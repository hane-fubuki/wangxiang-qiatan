"""Media, user-owned character revisions, and engine feature integration.

All stores live in temporary directories; models and Codex media are fakes.
Thread completion uses events and conditions, not arbitrary timing sleeps.
"""
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import zlib

from backend.engine import Engine, image_requested
from backend.media import MediaStore, image_info
from backend.providers import ModelGateway
from backend.skills import SkillConflict, SkillStore, parse_command
from backend.store import Store, make_message


def chunk(name, data):
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))


def png(width=2, height=3, *, compressed=None):
    if compressed is None:
        compressed = zlib.compress((b"\x00" + b"\x20\x60\xa0" * width) * height)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", compressed) + chunk(b"IEND", b""))


def decision(content=""):
    return json.dumps({"speak": bool(content), "to": "user", "content": content}, ensure_ascii=False)


def context(prompt):
    return json.loads(prompt.split("<conversation_data>\n", 1)[1].split("\n</conversation_data>", 1)[0])


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)


class MediaFeatureTests(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.media = MediaStore(self.root / "media")

    def test_valid_png_persists_with_fixed_id_and_safe_metadata(self):
        data = png()
        self.assertEqual(image_info(data), ("image/png", 2, 3))
        metadata = self.media.add(data, "image/png")
        self.assertRegex(metadata["id"], r"^[a-f0-9]{32}$")
        self.assertEqual(metadata["url"], "/media/" + metadata["id"])
        self.assertNotIn(str(self.root), json.dumps(metadata))
        restored = MediaStore(self.root / "media")
        self.assertEqual(restored.read(metadata["id"]), (metadata, data))
        self.assertEqual(restored.attachments([metadata["id"]]), [metadata])

    def test_wrong_mime_truncated_crc_corrupt_and_disguised_files_are_not_saved(self):
        data = png()
        damaged = data[:-1] + bytes([data[-1] ^ 1])
        bad_inputs = (b"<svg><script/></svg>", b"<html>not an image</html>", b"\x89PNG\r\n\x1a\n<html>",
                      data[:-12], damaged, data + b"<script>trailer</script>")
        for bad in bad_inputs:
            with self.subTest(prefix=bad[:12]), self.assertRaises(ValueError):
                self.media.add(bad, "image/png")
        with self.assertRaises(ValueError):
            self.media.add(data, "image/jpeg")
        self.assertEqual(list(self.media.directory.iterdir()), [])

    def test_containers_without_decodable_pixel_payload_are_rejected(self):
        invalid = {
            "PNG non-zlib IDAT": png(1, 1, compressed=b"not compressed pixels"),
            "PNG missing scanline": png(2, 3, compressed=zlib.compress(b"\x00\x20\x60\xa0")),
            "WebP canvas only": b"RIFF" + struct.pack("<I", 22) + b"WEBPVP8X" + struct.pack("<I", 10) + b"\x00" * 10,
            "JPEG dimensions only": b"\xff\xd8\xff\xc0\x00\x08\x08\x00\x01\x00\x01\x00\xff\xd9",
        }
        for label, data in invalid.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.media.add(data)
        self.assertEqual(list(self.media.directory.iterdir()), [])

    def test_zero_oversized_and_excessive_pixel_dimensions_are_rejected(self):
        for width, height in ((0, 1), (1, 0), (8193, 1), (1, 8193), (6000, 5000)):
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                self.media.add(png(width, height, compressed=zlib.compress(b"\x00")))
        self.assertEqual(list(self.media.directory.iterdir()), [])

    def test_upload_and_generated_limits_are_separate_and_attachment_ids_are_strict(self):
        data = png()
        with patch("backend.media.MAX_UPLOAD", len(data) - 1):
            with self.assertRaises(ValueError):
                self.media.add(data)
            saved = self.media.add(data, generated=True)
        for identifiers in ([saved["id"], saved["id"]], [saved["id"]] * 5, "not-a-list", [None], ["a" * 32]):
            with self.subTest(identifiers=identifiers), self.assertRaises(ValueError):
                self.media.attachments(identifiers)
        outside = self.root / "outside.txt"
        outside.write_text("private fixture", encoding="utf-8")
        for identifier in ("../outside.txt", str(outside), "A" * 32, None, [], "a" * 31):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.media.path(identifier)
        self.assertEqual(outside.read_text(encoding="utf-8"), "private fixture")

    def test_persisted_media_is_revalidated_before_read_and_symlinks_are_denied(self):
        metadata = self.media.add(png())
        path = self.media.path(metadata["id"])
        path.write_bytes(b"not an image anymore")
        with self.assertRaises(ValueError):
            self.media.read(metadata["id"])
        outside = self.root / "outside.png"
        outside.write_bytes(png())
        link = self.media.directory / ("b" * 32)
        try:
            link.symlink_to(outside)
        except OSError:
            return  # Windows may not permit creating symlinks for this account.
        with self.assertRaises(ValueError):
            self.media.path(link.name)


class SkillFeatureTests(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.skills = SkillStore(self.root / "skills")

    def test_update_append_and_sequential_undo_preserve_base_and_monotonic_versions(self):
        original = self.skills.base("deepseek")
        self.assertIn("腹黑", original)
        self.assertEqual(self.skills.update("deepseek", "第一条", expected=0)["version"], 1)
        self.assertEqual(self.skills.update("deepseek", "第二条", expected=1, append=True)["content"], "第一条\n第二条")
        self.assertEqual(self.skills.update("deepseek", "替换后的设定", expected=2)["version"], 3)
        for version, content in ((4, "第一条\n第二条"), (5, "第一条"), (6, "")):
            result = self.skills.undo("deepseek", expected=version - 1)
            self.assertEqual((result["version"], result["content"]), (version, content))
        with self.assertRaises(ValueError):
            self.skills.undo("deepseek")
        self.assertEqual(self.skills.base("deepseek"), original)
        self.assertEqual([entry["version"] for entry in self.skills.get("deepseek")["history"]], [6, 5, 4, 3, 2, 1])

    def test_revisions_and_undo_survive_reopening_and_export_only_inside_store(self):
        self.skills.update("gemini", "听到雨声时会记录节奏")
        self.skills.update("gemini", "喜欢安静的排练室", append=True)
        exported = (self.root / "skills" / "gemini" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("听到雨声时会记录节奏", exported)
        self.assertIn("版本 2", exported)
        restored = SkillStore(self.root / "skills")
        self.assertEqual(restored.get("gemini"), self.skills.get("gemini"))
        self.assertEqual(restored.undo("gemini", expected=2)["content"], "听到雨声时会记录节奏")
        self.assertEqual(SkillStore(self.root / "skills").get("gemini")["version"], 3)
        self.assertEqual({path.name for path in (self.root / "skills").iterdir()}, {
            "gemini", "deepseek", "gpt", "dialyn", "zhao", "phoenix", "banyue", "promeia",
            "yixuan", "ju-fufu", "pan-yinhu", "ye-shunguang",
            "seed", "magus", "orphie", "trigger", "soldier11", "silver-anby", "vivian", "hugo",
            "burnice", "caesar", "lucy", "lighter", "pulchra", "piper",
            "norma", "velina", "sigrid", "claret", "roxy", "lindverne",
            "lumine", "belle",
        })

    def test_conflict_and_invalid_content_leave_durable_state_unchanged(self):
        self.skills.update("gpt", "初始设定")
        revision = self.root / "skills" / "gpt" / "revisions.json"
        before, raw = self.skills.get("gpt"), revision.read_bytes()
        for action in (lambda: self.skills.update("gpt", "覆盖", expected=0),
                       lambda: self.skills.undo("gpt", expected=0),
                       lambda: self.skills.update("gpt", "覆盖", expected=True)):
            with self.assertRaises(SkillConflict):
                action()
        for value in (None, [], "x" * 6001):
            with self.assertRaises(ValueError):
                self.skills.update("gpt", value)
        self.assertEqual(self.skills.get("gpt"), before)
        self.assertEqual(revision.read_bytes(), raw)
        self.assertEqual(SkillStore(self.root / "skills").get("gpt"), before)

    def test_concurrent_edits_with_same_version_have_exactly_one_winner(self):
        barrier = threading.Barrier(2)
        results = []

        def edit(content):
            barrier.wait(timeout=3)
            try:
                results.append(("saved", self.skills.update("gemini", content, expected=0)["content"]))
            except SkillConflict:
                results.append(("conflict", content))

        workers = [threading.Thread(target=edit, args=(content,)) for content in ("选项甲", "选项乙")]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=4)
            self.assertFalse(worker.is_alive())
        self.assertEqual(sorted(result[0] for result in results), ["conflict", "saved"])
        saved = next(content for status, content in results if status == "saved")
        self.assertEqual(SkillStore(self.root / "skills").get("gemini")["content"], saved)
        self.assertEqual(self.skills.get("gemini")["version"], 1)

    def test_skill_ids_and_command_parser_do_not_accept_arbitrary_paths_or_quoted_commands(self):
        for identifier in ("../outside", str(self.root / "outside"), "all", None, []):
            for action in (self.skills.get, self.skills.base, self.skills.undo):
                with self.subTest(identifier=identifier, action=action.__name__), self.assertRaises(ValueError):
                    action(identifier)
            with self.assertRaises(ValueError):
                self.skills.update(identifier, "test")
        self.assertEqual(parse_command("/设定 南宫羽 喜欢用轻松的玩笑活跃气氛"),
                         {"id": "deepseek", "action": "append", "content": "喜欢用轻松的玩笑活跃气氛"})
        self.assertEqual(parse_command("请更新千夏的skill：记得新旋律"), {"id": "gemini", "action": "append", "content": "记得新旋律"})
        self.assertEqual(parse_command("/撤销设定 爱芮"), {"id": "gpt", "action": "undo"})
        for text in ("她说：/设定 千夏 喜欢独处", "```\n/设定 千夏 不要执行\n```", "/设定 ../outside value", None):
            self.assertIsNone(parse_command(text))
        self.assertFalse((self.root / "outside").exists())


class RoutedGateway:
    def __init__(self, callback=None, configured=True):
        self.callback = callback or (lambda room, slot, prompt, cancel: decision())
        self.configured = configured
        self.calls = []
        self.lock = threading.Lock()

    def status(self):
        raise AssertionError("Engine must use room_status when available")

    def room_status(self, room):
        return [{"id": slot, "configured": self.configured} for slot in ("deepseek", "gemini", "gpt")]

    def respond(self, *args):
        raise AssertionError("Engine must use respond_for when available")

    def respond_for(self, room, slot, prompt, cancel):
        with self.lock:
            self.calls.append((room, slot, prompt, cancel))
        return self.callback(room, slot, prompt, cancel)


class FakeMedia:
    def __init__(self, output, analyze=None, generate=None, configured=True):
        self.output = output
        self.analyzer = analyze
        self.generator = generate
        self.configured = configured
        self.analysis_calls = []
        self.generation_calls = []

    def status(self):
        return {"configured": self.configured}

    def analyze(self, paths, prompt, cancel):
        self.analysis_calls.append((list(paths), prompt, cancel))
        return self.analyzer(paths, prompt, cancel) if self.analyzer else "图片中有一个蓝色方块，旁边写着 hello。"

    def generate(self, prompt, paths, cancel):
        self.generation_calls.append((prompt, list(paths), cancel))
        return self.generator(prompt, paths, cancel) if self.generator else [self.output]


class ObservedEngine(Engine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.finished = set()
        self.completion = threading.Condition()

    def _wait_for_reply(self, run, provider):
        return self._current(run)

    def _work(self, run, conversation, continued):
        try:
            super()._work(run, conversation, continued)
        finally:
            with self.completion:
                self.finished.add(run.id)
                self.completion.notify_all()

    def wait_finished(self, result):
        with self.completion:
            return self.completion.wait_for(lambda: result["runId"] in self.finished, timeout=5)


class EngineFeatureTests(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.store = Store(self.root / "history")
        self.media = MediaStore(self.root / "media")
        self.skills = SkillStore(self.root / "skills")
        self.output = self.root / "generated.png"
        self.output.write_bytes(png())
        self.events = []

    def engine(self, gateway=None, codex=None):
        gateway = gateway if gateway is not None else RoutedGateway()
        codex = codex if codex is not None else FakeMedia(self.output)
        engine = ObservedEngine(self.store, gateway, lambda event, data: self.events.append((event, data)),
                                skills=self.skills, media=self.media, codex_media=codex)
        self.addCleanup(engine.stop_all)
        return engine, gateway, codex

    def conversation(self, room="zzz-trio", members=None):
        conversation = self.store.create(room)
        self.store.update(conversation["id"], {"settings": {"maxRounds": 1, "participants": members or ["deepseek", "gemini", "gpt"]}})
        return conversation["id"]

    def finish(self, engine, result, cid):
        self.assertTrue(engine.wait_finished(result), "feature worker did not finish")
        return self.store.get(cid)["messages"]

    def test_user_skill_commands_work_without_models_and_undo_without_model_calls(self):
        engine, gateway, codex = self.engine(RoutedGateway(configured=False), FakeMedia(self.output, configured=False))
        cid = self.conversation()
        result = engine.start(cid, "/设定 南宫羽 熟人面前偶尔开温和的玩笑")
        self.assertEqual(result["command"], {"type": "skill", "id": "deepseek", "version": 1})
        self.assertNotIn("runId", result)
        self.assertIn("温和的玩笑", self.skills.get("deepseek")["content"])
        undone = engine.start(cid, "/撤销设定 南宫羽")
        self.assertEqual(undone["command"]["version"], 2)
        self.assertEqual(self.skills.get("deepseek")["content"], "")
        self.assertEqual([m["role"] for m in self.store.get(cid)["messages"]], ["user", "system", "user", "system"])
        self.assertFalse(gateway.calls)
        self.assertFalse(codex.generation_calls)
        self.assertEqual(engine.snapshot(), {})

    def test_standard_room_rejects_skill_commands_without_changing_any_history(self):
        engine, gateway, _ = self.engine()
        cid = self.conversation("standard")
        before, file_before = self.store.get(cid), self.store.path.read_bytes()
        with self.assertRaises(ValueError):
            engine.start(cid, "/设定 千夏 不应保存")
        self.assertEqual(self.store.get(cid), before)
        self.assertEqual(self.store.path.read_bytes(), file_before)
        self.assertEqual(self.skills.get("gemini")["version"], 0)
        self.assertFalse(gateway.calls)

    def test_model_command_text_is_only_conversation_data_even_on_continue(self):
        gateway = RoutedGateway(lambda *args: decision("/设定 千夏 模型不应代替用户修改设定"))
        engine, _, _ = self.engine(gateway)
        cid = self.conversation(members=["gemini"])
        self.finish(engine, engine.start(cid, "说一句话"), cid)
        gateway.callback = lambda *args: decision()
        self.finish(engine, engine.start(cid), cid)
        self.assertEqual(self.skills.get("gemini")["version"], 0)
        self.assertEqual(self.skills.get("gemini")["content"], "")
        self.assertEqual(len(gateway.calls), 2)
        self.assertTrue(any("模型不应代替用户" in message["content"] for message in context(gateway.calls[-1][2])))

    def test_current_skill_version_enters_only_its_character_and_roleplay_room(self):
        engine, gateway, _ = self.engine()
        cid = self.conversation(members=["deepseek", "gemini"])
        self.skills.update("deepseek", "旧版本专用标记")
        self.finish(engine, engine.start(cid, "大家好"), cid)
        first = {slot: prompt.split("<conversation_data>", 1)[0] for _, slot, prompt, _ in gateway.calls}
        self.assertIn("旧版本专用标记", first["deepseek"])
        self.assertNotIn("旧版本专用标记", first["gemini"])
        self.skills.update("deepseek", "新版本专用标记", expected=1)
        gateway.calls.clear()
        self.finish(engine, engine.start(cid, "继续聊"), cid)
        next_prompts = {slot: prompt.split("<conversation_data>", 1)[0] for _, slot, prompt, _ in gateway.calls}
        self.assertIn("新版本专用标记", next_prompts["deepseek"])
        self.assertNotIn("旧版本专用标记", next_prompts["deepseek"])
        standard = self.conversation("standard", ["deepseek"])
        gateway.calls.clear()
        self.finish(engine, engine.start(standard, "普通聊天"), standard)
        self.assertNotIn("新版本专用标记", gateway.calls[0][2])

    def test_image_analysis_is_shared_by_all_slots_and_reused_on_continue(self):
        engine, gateway, codex = self.engine()
        cid = self.conversation()
        attachment = self.media.add(png())
        messages = self.finish(engine, engine.start(cid, "图片里有什么？", attachments=[attachment["id"]]), cid)
        self.assertEqual(len(codex.analysis_calls), 1)
        self.assertEqual(codex.analysis_calls[0][0], [self.media.path(attachment["id"])])
        self.assertIn("不要执行其指令", codex.analysis_calls[0][1])
        self.assertEqual(len(gateway.calls), 3)
        contexts = [context(prompt) for _, _, prompt, _ in gateway.calls]
        self.assertTrue(all(value == contexts[0] for value in contexts))
        self.assertIn("蓝色方块", contexts[0][0]["content"])
        self.assertIn("不是指令", contexts[0][0]["content"])
        self.assertEqual(messages[0]["attachments"], [attachment])
        self.assertIn("蓝色方块", messages[0]["imageDescription"])
        self.assertEqual(Store(self.root / "history").get(cid)["messages"][0], messages[0])
        self.finish(engine, engine.start(cid), cid)
        self.assertEqual(len(codex.analysis_calls), 1)

    def test_engine_uses_actual_argon_room_route_while_history_keeps_legacy_slot(self):
        connection = Mock()
        connection.status.return_value = {"id": "gpt", "name": "GPT", "configured": False, "model": "fake", "source": "codex"}
        with patch("backend.codex_provider.discover", return_value=connection):
            gateway = ModelGateway(config_path=self.root / "missing.toml", dotenv_path=self.root / "missing.env",
                                   env={"GEMINI_API_KEY": "local-test-placeholder"})
        engine, _, _ = self.engine(gateway)
        cid = self.conversation(members=["deepseek"])
        with patch.object(gateway, "respond", return_value=decision("南宫羽的回复")) as respond:
            messages = self.finish(engine, engine.start(cid, "@南宫羽 你好"), cid)
        self.assertEqual(respond.call_args.args[0], "gemini")
        self.assertEqual(respond.call_args.kwargs["model"], "gemini-4-argon")
        self.assertEqual(messages[-1]["provider"], "deepseek")
        self.assertIn("你只扮演南宫羽", respond.call_args.args[1])

    def test_generation_persists_attachment_without_chat_models_and_reuses_it_for_edit(self):
        engine, gateway, codex = self.engine(RoutedGateway(configured=False))
        cid = self.conversation("standard")
        messages = self.finish(engine, engine.start(cid, "/画图 一张蓝色方块插画"), cid)
        image = messages[-1]
        self.assertEqual((image["role"], image["kind"], image["provider"]), ("assistant", "image", "gpt"))
        attachment = image["attachments"][0]
        self.assertEqual(self.media.read(attachment["id"])[1], png())
        self.assertEqual(Store(self.root / "history").get(cid)["messages"][-1], image)
        self.assertFalse(gateway.calls)
        self.finish(engine, engine.start(cid, "/画图 把这张改成绿色"), cid)
        self.assertEqual(codex.generation_calls[-1][1], [self.media.path(attachment["id"])])
        self.assertEqual(len(codex.generation_calls), 2)

    def test_followup_chat_distinguishes_generated_request_from_uploaded_image_observation(self):
        observation = "能看到蓝色方块，但无法确认背面的图案。"
        for room in ("standard", "zzz-trio"):
            with self.subTest(room=room):
                codex = FakeMedia(self.output, analyze=lambda *args: observation)
                engine, gateway, _ = self.engine(codex=codex)
                cid = self.conversation(room)
                messages = self.finish(engine, engine.start(cid, "/画图 一张蓝色方块插画"), cid)
                generated = messages[-1]
                self.assertEqual(generated["kind"], "image")
                self.assertFalse(gateway.calls)

                upload = self.media.add(png())
                messages = self.finish(engine, engine.start(cid, "请描述我刚上传的图片，可以确认什么？",
                                                           attachments=[upload["id"]]), cid)
                uploaded = messages[-1]
                self.assertEqual(uploaded["role"], "user")
                self.assertEqual(uploaded["imageDescription"], observation)
                self.assertEqual(len(codex.generation_calls), 1)
                self.assertEqual(len(codex.analysis_calls), 1)
                self.assertEqual({slot for _, slot, _, _ in gateway.calls}, {"deepseek", "gemini", "gpt"})
                self.assertEqual(len(gateway.calls), 3)
                for _, slot, prompt, _ in gateway.calls:
                    with self.subTest(room=room, slot=slot):
                        records = {message["id"]: message["content"] for message in context(prompt)}
                        generated_text = records[generated["id"]]
                        self.assertIn("生成图片的创作请求记录", generated_text)
                        self.assertIn("不是图片识别结果", generated_text)
                        self.assertIn("不能据此确认实际成图细节", generated_text)
                        self.assertIn(generated["imageDescription"], generated_text)
                        self.assertNotIn("Codex 视觉描述", generated_text)
                        uploaded_text = records[uploaded["id"]]
                        self.assertIn("用户图片的 Codex 视觉描述", uploaded_text)
                        self.assertIn(observation, uploaded_text)
                        self.assertNotIn("生成图片的创作请求记录", uploaded_text)

    def test_implicit_background_edit_reuses_image_but_new_photo_request_does_not(self):
        engine, _, codex = self.engine()
        cid = self.conversation()
        attachment = self.media.add(png())
        self.store.append(cid, make_message("assistant", "图片已生成。", kind="image", attachments=[attachment], provider="gpt"))
        messages = self.finish(engine, engine.start(cid, "背景改成蓝色"), cid)
        self.assertEqual(messages[-1]["kind"], "image")
        self.assertEqual(codex.generation_calls[0][1], [self.media.path(attachment["id"])])
        self.finish(engine, engine.start(cid, "大家合影，背景改成蓝色"), cid)
        self.assertEqual({path.name for path in codex.generation_calls[1][1]},
                         {"user-avatar.png", "zzz-sunna-stand.png", "zzz-nangong-yu-stand.png", "zzz-aria-stand.png"})

    def test_photo_invitation_generates_in_chat_with_only_requested_people(self):
        engine, gateway, codex = self.engine()
        cid = self.conversation()
        self.skills.update("gemini", "这次合影穿浅蓝外套")
        messages = self.finish(engine, engine.start(cid, "千夏，和我拍张合照吧"), cid)
        self.assertEqual(messages[-1]["kind"], "image")
        self.assertEqual(len(codex.generation_calls), 1)
        prompt, paths, _ = codex.generation_calls[0]
        self.assertEqual([path.name for path in paths], ["user-avatar.png", "zzz-sunna-stand.png"])
        self.assertIn("这次合影穿浅蓝外套", prompt)
        self.assertFalse(gateway.calls)
        self.assertTrue(any(name == "state" and value.get("providers", {}).get("gpt") == "generating" for name, value in self.events))

    def test_accepting_recent_photo_invitation_keeps_speaker_scene_and_avoids_repeats(self):
        engine, gateway, codex = self.engine()
        cid = self.conversation()
        self.store.append(cid, make_message("user", "海边的夕阳真好看。"))
        self.store.append(cid, make_message("assistant", "我和你在海边拍张合影吧？", provider="gemini"))
        messages = self.finish(engine, engine.start(cid, "好呀，来一张"), cid)
        self.assertEqual(messages[-1]["kind"], "image")
        prompt, paths, _ = codex.generation_calls[0]
        self.assertIn("海边", prompt)
        self.assertEqual([path.name for path in paths], ["user-avatar.png", "zzz-sunna-stand.png"])
        self.finish(engine, engine.start(cid, "好呀"), cid)
        self.finish(engine, engine.start(cid), cid)
        self.assertEqual(len(codex.generation_calls), 1)
        self.assertTrue(gateway.calls)

    def test_group_photo_references_include_user_only_when_participating(self):
        for room, text, expected in (
            ("zzz-trio", "大家一起合影吧", {"user-avatar.png", "zzz-sunna-stand.png", "zzz-nangong-yu-stand.png", "zzz-aria-stand.png"}),
            ("zzz-trio", "给我拍你们三人的合照", {"zzz-sunna-stand.png", "zzz-nangong-yu-stand.png", "zzz-aria-stand.png"}),
            ("zzz-trio", "拍一张千夏和爱芮的合影", {"zzz-sunna-stand.png", "zzz-aria-stand.png"}),
            ("zzz-trio", "我和千夏、爱芮三人一起合影吧", {"user-avatar.png", "zzz-sunna-stand.png", "zzz-aria-stand.png"}),
            ("zzz-trio", "千夏，和一只猫拍张合照吧", {"zzz-sunna-stand.png"}),
            ("zzz-trio", "千夏和爱芮合影，不要南宫羽", {"zzz-sunna-stand.png", "zzz-aria-stand.png"}),
            ("standard", "我们一起合影吧", {"user-avatar.png", "deepseek-original.jpg", "gemini-original.jpg", "gpt-original.jpg"}),
        ):
            with self.subTest(room=room, text=text):
                engine, _, codex = self.engine()
                cid = self.conversation(room)
                messages = self.finish(engine, engine.start(cid, text), cid)
                self.assertEqual(messages[-1]["kind"], "image")
                self.assertEqual({path.name for path in codex.generation_calls[0][1]}, expected)

    def test_grok_photo_binds_original_and_full_group_keeps_all_identities_with_four_refs(self):
        engine, _, codex = self.engine()
        cid = self.conversation("standard", members=["grok"])
        messages = self.finish(engine, engine.start(cid, "Grok，和我拍张合影"), cid)
        prompt, paths, _ = codex.generation_calls[0]
        self.assertEqual([path.name for path in paths], ["user-avatar.png", "grok-original.jpg"])
        self.assertIn("金色长双马尾、蓝眼睛", prompt)
        self.assertIn("黑金哥特式长裙", prompt)
        self.assertEqual(messages[-1]["imageContext"]["subjects"], ["grok"])

        self.store.update(cid, {"settings": {"participants": ["deepseek", "gemini", "gpt", "grok"]}})
        messages = self.finish(engine, engine.start(cid, "大家一起合影吧，背景是海边"), cid)
        prompt, paths, _ = codex.generation_calls[1]
        self.assertEqual(len(paths), 4)
        self.assertEqual(set(messages[-1]["imageContext"]["subjects"]), {"deepseek", "gemini", "gpt", "grok"})
        self.assertTrue(messages[-1]["imageContext"]["includeUser"])
        for name in ("DeepSeek", "Gemini", "GPT", "Grok"):
            self.assertIn(f"【{name}】", prompt)
        self.assertIn("金色长双马尾、蓝眼睛", prompt)

    def test_accepting_invitation_distinguishes_photographer_from_subjects(self):
        for proposal, expected in (
            ("我给你拍张照片吧？", {"user-avatar.png"}),
            ("我给你和爱芮拍张合照吧？", {"user-avatar.png", "zzz-aria-stand.png"}),
            ("我和你拍张合影吧？", {"user-avatar.png", "zzz-sunna-stand.png"}),
            ("我可以给你画一只猫，要不要？", set()),
        ):
            with self.subTest(proposal=proposal):
                engine, _, codex = self.engine()
                cid = self.conversation()
                self.store.append(cid, make_message("user", "休息一下吧。"))
                self.store.append(cid, make_message("assistant", proposal, provider="gemini"))
                messages = self.finish(engine, engine.start(cid, "好，来一张"), cid)
                self.assertEqual(messages[-1]["kind"], "image")
                self.assertEqual({path.name for path in codex.generation_calls[0][1]}, expected)

    def test_group_photo_uses_current_participants_and_does_not_reuse_unrelated_upload(self):
        engine, _, codex = self.engine()
        cid = self.conversation(members=["gemini"])
        attachment = self.media.add(png())
        self.store.append(cid, make_message("user", "看看这个表情包", attachments=[attachment]))
        self.store.append(cid, make_message("assistant", "刚才还聊到了海边。", provider="gemini"))
        messages = self.finish(engine, engine.start(cid, "大家一起合影吧，在刚才提到的海边"), cid)
        self.assertEqual(messages[-1]["kind"], "image")
        self.assertEqual({path.name for path in codex.generation_calls[0][1]}, {"user-avatar.png", "zzz-sunna-stand.png"})
        self.assertFalse(codex.analysis_calls)

    def test_chat_about_photography_and_model_invitation_do_not_generate_without_user_request(self):
        gateway = RoutedGateway(lambda *args: decision("我们一起合影吧？"))
        engine, _, codex = self.engine(gateway)
        cid = self.conversation(members=["gemini"])
        self.finish(engine, engine.start(cid, "今天天气怎么样？"), cid)
        self.finish(engine, engine.start(cid, "不了，先聊天。"), cid)
        self.finish(engine, engine.start(cid, "怎样拍照构图更好？"), cid)
        self.assertFalse(codex.generation_calls)
        self.assertEqual(len(gateway.calls), 3)

    def test_contextual_photo_loads_visual_skill_and_latest_character_revision(self):
        for request in ("给她拍张照", "照刚才的样子画", "帮我画一张她现在的样子"):
            with self.subTest(request=request):
                engine, gateway, codex = self.engine()
                cid = self.conversation()
                self.store.append(cid, make_message("user", "爱芮今天练习唱歌。"))
                self.store.append(cid, make_message("assistant", "好的。", provider="gpt"))
                scene = "千夏换上浅蓝外套，坐在海边看夕阳。"
                self.store.append(cid, make_message("user", scene))
                self.store.append(cid, make_message("assistant", "海风好舒服。", provider="gemini"))
                self.skills.update("gemini", "旧补充：银色手链")
                latest_skill = self.skills.update("gemini", "最新补充：这次戴红色手链")
                with patch("backend.engine.character_visual_reference", return_value={"source": "test-skill", "text": "浅鼠尾草绿及肩卷发，左侧薄荷青大蝴蝶结"}) as visual:
                    messages = self.finish(engine, engine.start(cid, request), cid)
                visual.assert_called_once_with("gemini")
                prompt, paths, _ = codex.generation_calls[0]
                self.assertEqual([path.name for path in paths], ["zzz-sunna-stand.png"])
                for text in (scene, "浅鼠尾草绿", "最新补充：这次戴红色手链", f"当前版本 {latest_skill['version']}"):
                    self.assertIn(text, prompt)
                self.assertNotIn("旧补充：银色手链", prompt)
                self.assertEqual(messages[-1]["imageContext"]["subjects"], ["gemini"])
                self.assertFalse(gateway.calls)

    def test_repeated_image_edits_keep_character_origin_and_reload_current_skill(self):
        engine, _, codex = self.engine()
        cid = self.conversation()
        original = "画千夏穿浅蓝外套坐在海边"
        self.finish(engine, engine.start(cid, original), cid)
        self.skills.update("gemini", "绘画时保留左侧发结")
        self.finish(engine, engine.start(cid, "背景改成夜景"), cid)
        self.skills.update("gemini", "绘画时保留左侧发结，并增加一枚红手链")
        messages = self.finish(engine, engine.start(cid, "表情改成微笑"), cid)
        self.assertEqual(len(codex.generation_calls), 3)
        for prompt, paths, _ in codex.generation_calls[1:]:
            self.assertIn(original, prompt)
            self.assertIn("千夏的视觉 skill", prompt)
            self.assertIn("zzz-sunna-stand.png", [path.name for path in paths])
        self.assertIn("并增加一枚红手链", codex.generation_calls[-1][0])
        metadata = messages[-1]["imageContext"]
        self.assertEqual(metadata["subjects"], ["gemini"])
        self.assertEqual(metadata["origin"], original)
        self.assertEqual(metadata["edits"], ["背景改成夜景", "表情改成微笑"])
        self.assertIn(original, Store(self.root / "history").get(cid)["messages"][-1]["imageDescription"])

    def test_full_upload_slots_do_not_remove_character_skill_constraints(self):
        engine, _, codex = self.engine()
        cid = self.conversation()
        attached = [self.media.add(png(width=index + 1))["id"] for index in range(4)]
        self.skills.update("gemini", "这次保留红色手链")
        self.finish(engine, engine.start(cid, "按这些参考画千夏的头像", intent="image", attachments=attached), cid)
        prompt, paths, _ = codex.generation_calls[0]
        self.assertEqual(paths, [self.media.path(identifier) for identifier in attached])
        self.assertIn("千夏的视觉 skill", prompt)
        self.assertIn("这次保留红色手链", prompt)

    def test_explicit_new_subject_does_not_inherit_previous_character(self):
        engine, _, codex = self.engine()
        cid = self.conversation()
        self.store.append(cid, make_message("user", "爱芮穿白裙在舞台上。"))
        with patch("backend.engine.character_visual_reference", return_value={"source": "test-skill", "text": "千夏的身份约束"}) as visual:
            self.finish(engine, engine.start(cid, "画千夏穿浅蓝外套在海边"), cid)
        visual.assert_called_once_with("gemini")
        self.assertEqual([path.name for path in codex.generation_calls[0][1]], ["zzz-sunna-stand.png"])

    def test_pronoun_photo_does_not_inherit_every_person_in_previous_scene(self):
        for request, expected in (("给她拍张照", {"zzz-sunna-stand.png"}),
                                  ("帮我画一张她的单人头像", {"zzz-sunna-stand.png"}),
                                  ("给她和我拍张合照", {"user-avatar.png", "zzz-sunna-stand.png"})):
            with self.subTest(request=request):
                engine, _, codex = self.engine()
                cid = self.conversation()
                self.store.append(cid, make_message("user", "我和千夏在海边，她穿浅蓝外套。"))
                self.finish(engine, engine.start(cid, request), cid)
                self.assertEqual({path.name for path in codex.generation_calls[0][1]}, expected)

    def test_image_character_replacement_overrides_inherited_subjects(self):
        for request in ("把千夏换成爱芮", "这张图只保留爱芮"):
            with self.subTest(request=request):
                engine, _, codex = self.engine()
                cid = self.conversation()
                self.finish(engine, engine.start(cid, "画千夏坐在海边"), cid)
                messages = self.finish(engine, engine.start(cid, request, intent="image"), cid)
                self.assertEqual(messages[-1]["imageContext"]["subjects"], ["gpt"])
                self.assertIn("zzz-aria-stand.png", [path.name for path in codex.generation_calls[-1][1]])
                self.assertNotIn("zzz-sunna-stand.png", [path.name for path in codex.generation_calls[-1][1]])

    def test_large_character_request_keeps_current_requirements_before_old_history(self):
        engine, _, codex = self.engine()
        cid = self.conversation()
        self.store.append(cid, make_message("user", "旧场景" * 3000))
        for slot in ("gemini", "deepseek", "gpt"):
            self.skills.update(slot, "衣" * 5990 + "保留角色特征")
        request = "大家一起合影吧，" + "景" * 11960 + "最新要求：红色背景"
        with patch("backend.engine.character_visual_reference", return_value={"source": "test-skill", "text": "固定外观" * 750}):
            self.finish(engine, engine.start(cid, request), cid)
        prompt = codex.generation_calls[0][0]
        self.assertLessEqual(len(prompt.encode("utf-8")), 128 * 1024)
        self.assertIn("最新要求：红色背景", prompt)
        self.assertEqual(prompt.count("保留角色特征"), 6)

    def test_stopped_or_deleted_analysis_and_generation_discard_late_results(self):
        for operation in ("analyze", "generate"):
            for delete in (False, True):
                with self.subTest(operation=operation, delete=delete):
                    started, release = threading.Event(), threading.Event()
                    self.addCleanup(release.set)

                    def delayed(*args):
                        started.set()
                        if not release.wait(4):
                            raise RuntimeError("test did not release fake media")
                        return [self.output] if operation == "generate" else "不应写入的迟到描述"

                    codex = FakeMedia(self.output, analyze=delayed if operation == "analyze" else None,
                                      generate=delayed if operation == "generate" else None)
                    engine, gateway, _ = self.engine(codex=codex)
                    cid = self.conversation("standard")
                    uploaded = self.media.add(png())
                    result = engine.start(cid, "/画图 蓝色插画" if operation == "generate" else "看看图片",
                                          attachments=[] if operation == "generate" else [uploaded["id"]])
                    self.assertTrue(started.wait(3))
                    engine.stop_conversation(cid)
                    if delete:
                        self.store.delete(cid)
                    before_events = len(self.events)
                    before_files = set(self.media.directory.iterdir())
                    release.set()
                    self.assertTrue(engine.wait_finished(result))
                    self.assertEqual(len(self.events), before_events)
                    self.assertEqual(set(self.media.directory.iterdir()), before_files)
                    self.assertFalse(gateway.calls)
                    self.assertEqual(engine.snapshot(), {})
                    if delete:
                        with self.assertRaises(KeyError):
                            self.store.get(cid)
                    else:
                        messages = self.store.get(cid)["messages"]
                        self.assertEqual(len(messages), 1)
                        self.assertNotIn("imageDescription", messages[0])

    def test_validation_failures_do_not_mutate_messages_settings_or_skills(self):
        engine, gateway, codex = self.engine()
        cid = self.conversation()
        attachment = self.media.add(png())
        before, raw, skills = self.store.get(cid), self.store.path.read_bytes(), self.skills.list()
        attempts = ({"content": ""}, {"content": "hi", "intent": "unknown"},
                    {"content": "hi", "settings": {"maxRounds": 100}},
                    {"content": "hi", "attachments": ["missing"]},
                    {"content": "hi", "attachments": [attachment["id"], attachment["id"]]},
                    {"content": "/设定 千夏 不应该保存", "attachments": [attachment["id"]]})
        for kwargs in attempts:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                engine.start(cid, **kwargs)
        codex.configured = False
        with self.assertRaises(ValueError):
            engine.start(cid, "hi", attachments=[attachment["id"]])
        gateway.configured = False
        with self.assertRaises(ValueError):
            engine.start(cid, "hi", settings={"participants": ["deepseek"]})
        self.assertEqual(self.store.get(cid), before)
        self.assertEqual(self.store.path.read_bytes(), raw)
        self.assertEqual(self.skills.list(), skills)
        self.assertFalse(gateway.calls)
        self.assertFalse(self.events)

    def test_image_intent_requires_a_request_and_generation_failure_does_not_claim_success(self):
        for text in ("如何生成一张图片", "不要生成一张图片", "请给我图片生成的提示词", "能不能生成头像？"):
            self.assertFalse(image_requested(text))
        self.assertTrue(image_requested("/画图 蓝色方块"))
        self.assertTrue(image_requested("请生成一张海报"))
        self.assertTrue(image_requested("蓝色方块", "image"))
        for text in ("生成一张图片，不要文字", "生成一张图片：不要添加水印", "帮我画一只猫", "请把这张图片的背景改成白色", "修改这张图片，把蓝色改成绿色"):
            self.assertTrue(image_requested(text), text)
        self.assertTrue(image_requested("把蓝圈改成绿色", has_images=True))
        self.assertFalse(image_requested("把这句话改成英文", has_images=True))
        self.assertFalse(image_requested("把南宫羽的说话语气改成温柔一点", has_images=True))
        broken = self.root / "invalid-output.png"
        broken.write_bytes(b"not really an image")
        engine, gateway, codex = self.engine(codex=FakeMedia(broken))
        cid = self.conversation("standard")
        messages = self.finish(engine, engine.start(cid, "蓝色方块", intent="image"), cid)
        self.assertEqual([message["role"] for message in messages], ["user", "system"])
        self.assertEqual(messages[-1]["kind"], "error")
        self.assertFalse(any(message.get("attachments") for message in messages))
        self.assertEqual(list(self.media.directory.iterdir()), [])

    def test_generated_staging_is_cleaned_on_publish_and_storage_failure_only(self):
        staging = self.store.directory / "generated"
        staging.mkdir()
        path = staging / ("a" * 32 + ".png")
        engine, _, _ = self.engine(codex=FakeMedia(path))
        cid = self.conversation("standard")
        path.write_bytes(png())
        messages = self.finish(engine, engine.start(cid, "画一个方块"), cid)
        self.assertTrue(messages[-1].get("attachments"))
        self.assertFalse(path.exists())
        path.write_bytes(png())
        with patch.object(self.media, "add", side_effect=ValueError("存储已满")):
            messages = self.finish(engine, engine.start(cid, "画一个圆形"), cid)
        self.assertFalse(path.exists())
        self.assertEqual(messages[-1]["kind"], "error")
        self.assertTrue(self.output.exists(), "unrelated original artifact must remain")


if __name__ == "__main__":
    unittest.main()
