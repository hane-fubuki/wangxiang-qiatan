"""Scene privacy across current rooms and future metadata-defined rooms.

All histories and media are temporary; transport fakes exercise the real
orchestrator without requesting model replies, research, or generated images.
"""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from backend import rooms
from backend.engine import parse_decision
from backend.media import MediaStore
from backend.rooms import get_room
from backend.scenes import (
    current_scene, parse_scene_command, public_scene, shared_conversation,
    visible_conversation,
)
from backend.store import Store, make_message
from tests.test_features import FakeMedia, ObservedEngine, context, decision, png
from tests.test_reasoning import FakeResearch
from tests.test_wangsheng_engine import Gateway


CURRENT_ROOMS = tuple(rooms._ROOMS)


class UniversalSceneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "history")
        self.media = MediaStore(self.root / "media")
        self.output = self.root / "generated.png"
        self.output.write_bytes(png())

    def engine(self, callback=None, research=None, codex=None):
        gateway = Gateway(callback)
        engine = ObservedEngine(
            self.store, gateway, lambda *_: None, media=self.media,
            codex_media=codex or FakeMedia(self.output),
            research=research or FakeResearch(),
        )
        self.addCleanup(engine.stop_all)
        return engine, gateway

    def finish(self, engine, cid, content=None, settings=None, attachments=None):
        result = engine.start(cid, content, {
            "maxRounds": 1, "webSearch": "off", **(settings or {}),
        }, attachments=attachments)
        self.assertTrue(engine.wait_finished(result), result)
        messages = self.store.get(cid)["messages"]
        self.assertFalse([m for m in messages if m.get("kind") == "error"], messages)
        return messages

    def test_names_ids_and_user_aliases_resolve_in_every_room(self):
        for room_id in CURRENT_ROOMS:
            characters = get_room(room_id)["characters"]
            for slot, character in characters.items():
                for alias in (slot, character["name"], *character.get("aliases", [])):
                    with self.subTest(room=room_id, alias=alias):
                        scene, text = parse_scene_command(f"/私聊 {alias} | 一起喝茶", room_id)
                        self.assertEqual(scene["audience"], ["user", slot])
                        self.assertEqual(scene["kind"], "private")
                        self.assertEqual(text, "一起喝茶")
            slot = next(iter(characters))
            for alias in ("user", "我", "你", "用户"):
                with self.subTest(room=room_id, user=alias):
                    scene, _ = parse_scene_command(f"/悄悄话 {alias} {slot}", room_id)
                    self.assertEqual(scene["audience"], ["user", slot])

    def test_full_room_private_scene_is_valid_and_persists_without_fixed_cap(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                expected = public_scene(room_id)["audience"]
                scene, _ = parse_scene_command("/悄悄话 " + " ".join(expected), room_id)
                cid = self.store.create(room_id)["id"]
                self.store.set_scene(cid, scene)
                restored = Store(self.root / "history").get(cid)
                self.assertEqual(current_scene(restored), scene)
                self.assertEqual(scene["kind"], "private")
                self.assertEqual(scene["audience"], expected)
                self.assertEqual(
                    parse_scene_command("/全桌 | 又见面了", room_id),
                    (public_scene(room_id), "又见面了"),
                )

    def test_invalid_scene_members_never_change_persisted_history(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                slot = next(iter(get_room(room_id)["characters"]))
                scene, _ = parse_scene_command(f"/私聊 {slot}", room_id)
                self.store.set_scene(cid, scene)
                before = self.store.path.read_bytes()
                for command in (f"/悄悄话 {slot}", f"/私聊 {slot} {slot}",
                                "/私聊 not_in_this_room", "/全桌 user"):
                    with self.assertRaises(ValueError, msg=command):
                        parse_scene_command(command, room_id)
                for audience in (["user", slot, slot], ["user", "unknown_slot"], [slot]):
                    with self.assertRaises(ValueError, msg=str(audience)):
                        self.store.set_scene(cid, {**scene, "audience": audience})
                self.assertEqual(self.store.path.read_bytes(), before)

    def test_room_character_names_do_not_alias_other_rooms(self):
        for room_id, name in (("standard", "钟离"), ("zzz-trio", "胡桃"),
                              ("zzz-krampus", "千夏"), ("wangsheng-trio", "琉音")):
            with self.subTest(room=room_id, name=name), self.assertRaises(ValueError):
                parse_scene_command("/私聊 " + name, room_id)

    def test_new_messages_are_scoped_but_legacy_messages_remain_public(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                first, second = list(get_room(room_id)["characters"])[:2]
                legacy = make_message("user", "LEGACY_PUBLIC_GREETING")
                # This is an old on-disk record, intentionally lacking scene metadata.
                self.store.items[cid]["identityEpoch"] = "legacy"
                self.store.items[cid]["messages"].append(copy.deepcopy(legacy))
                scene, _ = parse_scene_command(f"/私聊 {first}", room_id)
                self.store.set_scene(cid, scene)
                for role, text in (("user", "PRIVATE_MESSAGE"), ("assistant", "PRIVATE_ANSWER"),
                                   ("system", "PRIVATE_NOTICE")):
                    self.store.append(cid, make_message(role, text))
                conversation = Store(self.root / "history").get(cid)
                for message in conversation["messages"][1:]:
                    self.assertEqual(message["audience"], ["user", first])
                    self.assertEqual(message["scene"], scene)
                hidden = visible_conversation(conversation, second)["messages"]
                self.assertEqual(hidden, [legacy])
                self.assertEqual(len(visible_conversation(conversation, first)["messages"]), 4)
                self.store.set_scene(cid, public_scene(room_id))
                self.assertEqual(shared_conversation(self.store.get(cid))["messages"], [legacy])
                self.store.append(cid, make_message("user", "PUBLIC_AGAIN"))
                final = self.store.get(cid)["messages"][-1]
                self.assertEqual(final["audience"], public_scene(room_id)["audience"])
                self.assertEqual(final["scene"]["kind"], "public")

    def test_future_room_supports_new_slots_aliases_and_more_than_seven_people(self):
        room_id = "future-garden"
        metadata = {
            "id": room_id, "name": "未来花园", "priority": 1,
            "characters": {f"guest_{index}": {
                "name": f"来客{index}", "aliases": [f"访客{index}"],
                "providerId": "gemini", "model": "gemini-4-argon",
            } for index in range(9)},
        }
        with patch.dict(rooms._ROOMS, {room_id: metadata}):
            expected = ["user", *metadata["characters"]]
            private, _ = parse_scene_command("/私聊 访客8", room_id)
            self.assertEqual(private["audience"], ["user", "guest_8"])
            scene, _ = parse_scene_command("/悄悄话 " + " ".join(expected), room_id)
            cid = self.store.create(room_id)["id"]
            self.store.set_scene(cid, scene)
            self.store.append(cid, make_message("assistant", "在未来房间里见面", provider="guest_8"))
            restored = Store(self.root / "history").get(cid)
            self.assertEqual(restored["scene"]["audience"], expected)
            self.assertEqual(restored["messages"][-1]["audience"], expected)
            reply = json.dumps({"speak": True, "content": "来客8，你觉得呢？", "to": "guest_8"})
            self.assertEqual(parse_decision(reply, targets=expected + ["everyone"])["to"], "guest_8")
            self.assertEqual(parse_decision(reply, targets=["user", "guest_0", "everyone"])["to"], "everyone")

    def test_only_present_roles_respond_then_continue_with_the_same_scene(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                slot = next(iter(get_room(room_id)["characters"]))
                engine, gateway = self.engine()
                messages = self.finish(engine, cid, f"/私聊 {slot} | PRIVATE_HELLO")
                self.assertEqual([c[1] for c in gateway.calls], [slot])
                private_id = current_scene(self.store.get(cid))["id"]
                gateway.calls.clear()
                continued = self.finish(engine, cid)
                self.assertEqual([c[1] for c in gateway.calls], [slot])
                self.assertEqual(current_scene(self.store.get(cid))["id"], private_id)
                self.assertTrue(all(m["audience"] == ["user", slot] for m in continued))
                self.assertFalse(any(m["content"].startswith("/私聊") for m in messages))

    def test_private_text_and_research_never_reach_absent_roles_or_shared_lookup(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                first, second = list(get_room(room_id)["characters"])[:2]
                research = FakeResearch(lambda prompt, _: {
                    "summary": "PRIVATE_EVIDENCE" if "PRIVATE_SECRET_123" in prompt else "PUBLIC_EVIDENCE",
                    "sources": [{"title": "Test evidence", "url": "https://www.python.org/"}], "elapsedMs": 1,
                })
                engine, gateway = self.engine(research=research)
                self.finish(engine, cid, f"/私聊 {first} | PRIVATE_SECRET_123",
                            {"participants": [first, second], "webSearch": "always"})
                self.assertEqual(len(research.calls), 1)
                self.assertIn("PRIVATE_SECRET_123", research.calls[0][0])
                gateway.calls.clear()
                self.finish(engine, cid, "/全桌 | 帮我查一下公开名词",
                            {"participants": [first, second], "webSearch": "always"})
                self.assertEqual(len(research.calls), 2)
                self.assertNotIn("PRIVATE_SECRET_123", research.calls[-1][0])
                self.assertNotIn("PRIVATE_EVIDENCE", research.calls[-1][0])
                by_slot = {slot: prompt for _, slot, prompt in gateway.calls}
                self.assertIn("PRIVATE_SECRET_123", by_slot[first])
                self.assertIn("PRIVATE_EVIDENCE", by_slot[first])
                self.assertNotIn("PRIVATE_SECRET_123", by_slot[second])
                self.assertNotIn("PRIVATE_EVIDENCE", by_slot[second])
                self.assertIn("PUBLIC_EVIDENCE", by_slot[second])

    def test_director_mode_does_not_treat_user_as_present_or_reply_to_absent_roles(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                members = list(get_room(room_id)["characters"])
                first, second = members[:2]
                absent = members[2] if len(members) > 2 else "user"

                def respond(room, slot, prompt, cancel):
                    self.assertIn("场外导演", prompt)
                    self.assertTrue(any(m.get("director") and m["speaker"] == "director"
                                        for m in context(prompt)))
                    return json.dumps({"speak": True, "content": f"{slot}：一起商量吧", "to": absent})

                engine, gateway = self.engine(respond)
                messages = self.finish(engine, cid, f"/悄悄话 {first} {second} | 两人讨论晚饭")
                self.assertEqual({call[1] for call in gateway.calls}, {first, second})
                self.assertTrue(next(m for m in messages if m["role"] == "user")["director"])
                for message in messages:
                    self.assertEqual(message["audience"], [first, second])
                    if message["role"] == "assistant":
                        self.assertEqual(message["replyTo"], "everyone")
                gateway.callback = lambda *args: decision("接着聊下去")
                messages = self.finish(engine, cid)
                self.assertTrue(all(m["replyTo"] != "user" for m in messages if m["role"] == "assistant"))

    def test_private_image_is_not_reused_for_public_analysis_or_absent_role(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                first, second = list(get_room(room_id)["characters"])[:2]
                secret, public = self.media.add(png(2, 3)), self.media.add(png(3, 3))
                codex = FakeMedia(self.output, analyze=lambda paths, *_: (
                    "PRIVATE_IMAGE_EVIDENCE" if self.media.path(secret["id"]) in paths else "PUBLIC_IMAGE_EVIDENCE"))
                engine, gateway = self.engine(codex=codex)
                self.finish(engine, cid, f"/私聊 {first} | PRIVATE_IMAGE_SECRET", attachments=[secret["id"]])
                codex.analysis_calls.clear()
                gateway.calls.clear()
                self.finish(engine, cid, "/全桌 | 看看这张图片", {"participants": [first, second]},
                            attachments=[public["id"]])
                self.assertEqual(len(codex.analysis_calls), 1)
                paths, prompt, _ = codex.analysis_calls[0]
                self.assertEqual(paths, [self.media.path(public["id"])])
                for private in ("PRIVATE_IMAGE_SECRET", "PRIVATE_IMAGE_EVIDENCE", secret["id"]):
                    self.assertNotIn(private, prompt)
                by_slot = {slot: prompt for _, slot, prompt in gateway.calls}
                self.assertIn("PRIVATE_IMAGE_EVIDENCE", by_slot[first])
                self.assertNotIn("PRIVATE_IMAGE_EVIDENCE", by_slot[second])

    def test_private_memory_query_cannot_leak_into_shared_research(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                first, second = list(get_room(room_id)["characters"])[:2]
                research = FakeResearch()
                engine, gateway = self.engine(research=research)
                self.finish(engine, cid, f"/私聊 {first} | SECRET_PRIVATE_QUERY")

                def respond(room, slot, prompt, cancel):
                    if slot == first and "已核对的背景知识" not in prompt:
                        return json.dumps({"speak": False, "to": "everyone", "content": "",
                                           "searchQuery": "SECRET_PRIVATE_QUERY"})
                    return decision("那我们先一起喝茶吧。")

                gateway.callback = respond
                self.finish(engine, cid, "/全桌 | 今天一起喝茶吧",
                            {"participants": [first, second], "webSearch": "auto"})
                self.assertEqual(len(research.calls), 1)
                self.assertNotIn("SECRET_PRIVATE_QUERY", research.calls[0][0])

    def test_private_group_photo_uses_only_current_roles_and_scopes_generated_message(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                first, second = list(get_room(room_id)["characters"])[:2]
                codex = FakeMedia(self.output)
                engine, gateway = self.engine(codex=codex)
                messages = self.finish(engine, cid,
                    f"/悄悄话 {first} {second} | 生成两人的合影，不带我")
                self.assertEqual(len(codex.generation_calls), 1)
                prompt, paths, _ = codex.generation_calls[0]
                self.assertIn("场外导演", prompt)
                self.assertNotIn("user-avatar.png", [path.name for path in paths])
                generated = next(message for message in messages if message.get("kind") == "image")
                self.assertEqual(generated["audience"], [first, second])
                self.assertEqual(generated["scene"]["kind"], "private")
                self.assertEqual(set(generated["imageContext"]["subjects"]), {first, second})
                self.assertFalse(generated["imageContext"]["includeUser"])
                self.assertEqual(gateway.calls, [])

    def test_continue_after_private_only_history_does_not_reveal_it_to_public_scene(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                slot = next(iter(get_room(room_id)["characters"]))
                engine, gateway = self.engine()
                self.finish(engine, cid, f"/私聊 {slot} | PRIVATE_ONLY")
                result = engine.start(cid, "/全桌")
                self.assertEqual(result["command"]["type"], "scene")
                gateway.calls.clear()
                with self.assertRaises(ValueError):
                    engine.start(cid)
                self.assertEqual(gateway.calls, [])

    def test_continue_cannot_attach_private_evidence_to_an_older_public_message(self):
        for room_id in CURRENT_ROOMS:
            for transition in ("public_to_private", "private_to_other_group"):
                with self.subTest(room=room_id, transition=transition):
                    cid = self.store.create(room_id)["id"]
                    first, second = list(get_room(room_id)["characters"])[:2]
                    private_a, _ = parse_scene_command(f"/私聊 {first}", room_id)
                    self.store.set_scene(cid, private_a)
                    secret_image = self.media.add(png(2, 3))
                    self.store.append(cid, make_message("user", "PRIVATE_CONTEXT_SECRET",
                        attachments=[secret_image], imageDescription="PRIVATE_IMAGE_SECRET"))
                    self.store.set_scene(cid, public_scene(room_id))
                    public_image = self.media.add(png(3, 3))
                    self.store.append(cid, make_message("user", "普通的公开话题", attachments=[public_image]))
                    if transition == "private_to_other_group":
                        self.store.set_scene(cid, private_a)
                        self.store.append(cid, make_message("user", "ONLY_FIRST_ROLE_KNOWS"))
                    research = FakeResearch()
                    codex = FakeMedia(self.output, analyze=lambda *_: "EVIDENCE_MUST_NOT_BE_WRITTEN")
                    engine, gateway = self.engine(research=research, codex=codex)
                    target = first if transition == "public_to_private" else second
                    switched = engine.start(cid, f"/私聊 {target}")
                    self.assertEqual(switched["command"]["type"], "scene")
                    before = self.store.get(cid)
                    disk_before = self.store.path.read_bytes()
                    result = None
                    try:
                        with self.assertRaisesRegex(ValueError, "先.*消息"):
                            result = engine.start(cid, None, {"maxRounds": 1, "webSearch": "always"})
                    finally:
                        # If the guard regresses, still join its worker before
                        # reporting failure or cleaning up temporary data.
                        if result and "runId" in result:
                            self.assertTrue(engine.wait_finished(result))
                    self.assertEqual(gateway.calls, [])
                    self.assertEqual(research.calls, [])
                    self.assertEqual(codex.analysis_calls, [])
                    self.assertEqual(codex.generation_calls, [])
                    self.assertEqual(self.store.get(cid), before)
                    self.assertEqual(self.store.path.read_bytes(), disk_before)

    def test_returning_to_table_continues_existing_public_prompt_without_private_evidence(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                first, second = list(get_room(room_id)["characters"])[:2]
                public_image = self.media.add(png(3, 3))
                self.store.append(cid, make_message("user", "PUBLIC_QUESTION", attachments=[public_image]))
                original = self.store.get(cid)["messages"][0]
                private, _ = parse_scene_command(f"/私聊 {first}", room_id)
                self.store.set_scene(cid, private)
                private_image = self.media.add(png(2, 3))
                self.store.append(cid, make_message("user", "PRIVATE_CONTEXT_SECRET",
                    attachments=[private_image], imageDescription="PRIVATE_IMAGE_SECRET"))
                private_message = self.store.get(cid)["messages"][-1]
                research = FakeResearch()
                codex = FakeMedia(self.output)
                engine, gateway = self.engine(research=research, codex=codex)
                engine.start(cid, "/全桌")
                messages = self.finish(engine, cid, settings={
                    "participants": [first, second], "webSearch": "always",
                })
                self.assertEqual(len(research.calls), 1)
                self.assertEqual(len(codex.analysis_calls), 1)
                paths, analysis_prompt, _ = codex.analysis_calls[0]
                self.assertEqual(paths, [self.media.path(public_image["id"])])
                for prompt in (research.calls[0][0], analysis_prompt):
                    self.assertNotIn("PRIVATE_CONTEXT_SECRET", prompt)
                    self.assertNotIn("PRIVATE_IMAGE_SECRET", prompt)
                    self.assertNotIn(private_image["id"], prompt)
                absent_prompt = next(prompt for _, slot, prompt in gateway.calls if slot == second)
                self.assertNotIn("PRIVATE_CONTEXT_SECRET", absent_prompt)
                self.assertNotIn("PRIVATE_IMAGE_SECRET", absent_prompt)
                saved_public = next(message for message in messages if message["id"] == original["id"])
                self.assertEqual(saved_public["audience"], original["audience"])
                self.assertEqual(saved_public["scene"], original["scene"])
                saved_private = next(message for message in messages if message["id"] == private_message["id"])
                self.assertEqual(saved_private, private_message)

    def test_same_audience_continue_needs_no_new_user_message_or_tool_reprocessing(self):
        for room_id in CURRENT_ROOMS:
            for kind in ("public", "private"):
                with self.subTest(room=room_id, kind=kind):
                    cid = self.store.create(room_id)["id"]
                    first = next(iter(get_room(room_id)["characters"]))
                    research = FakeResearch()
                    codex = FakeMedia(self.output)
                    engine, gateway = self.engine(research=research, codex=codex)
                    text = "今天一起喝茶吧" if kind == "public" else f"/私聊 {first} | 今天一起喝茶吧"
                    self.finish(engine, cid, text, {"participants": [first]})
                    original_messages = copy.deepcopy(self.store.get(cid)["messages"])
                    gateway.calls.clear()
                    messages = self.finish(engine, cid)
                    self.assertEqual([call[1] for call in gateway.calls], [first])
                    self.assertEqual(messages[:len(original_messages)], original_messages)
                    self.assertEqual(len(messages), len(original_messages) + 1)
                    self.assertEqual(messages[-1]["audience"], original_messages[-1]["audience"])
                    self.assertEqual(research.calls, [])
                    self.assertEqual(codex.analysis_calls, [])
                    self.assertEqual(codex.generation_calls, [])

    def test_scene_switch_cancels_inflight_reply_before_new_private_scene(self):
        for room_id in CURRENT_ROOMS:
            with self.subTest(room=room_id):
                cid = self.store.create(room_id)["id"]
                first, second = list(get_room(room_id)["characters"])[:2]
                entered, released = threading.Event(), threading.Event()

                def blocked(*args):
                    entered.set()
                    released.wait(timeout=3)
                    return decision("LATE_OLD_SCENE_REPLY")

                engine, gateway = self.engine(blocked)
                result = engine.start(cid, "先稍等", {"participants": [first], "maxRounds": 1, "webSearch": "off"})
                self.assertTrue(entered.wait(2))
                try:
                    switched = engine.start(cid, f"/私聊 {second}")
                    self.assertEqual(current_scene(switched["conversation"])["audience"], ["user", second])
                finally:
                    released.set()
                self.assertTrue(engine.wait_finished(result))
                self.assertNotIn("LATE_OLD_SCENE_REPLY", [m["content"] for m in self.store.get(cid)["messages"]])


if __name__ == "__main__":
    unittest.main()
