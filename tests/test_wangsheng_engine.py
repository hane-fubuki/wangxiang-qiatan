"""Real engine orchestration with fake transports and isolated visitor data."""
import json
from pathlib import Path
import tempfile
import threading
import unittest

from backend.engine import build_prompt, parse_decision, _public_terms
from backend.media import MediaStore
from backend.rooms import get_room
from backend.scenes import current_scene, shared_conversation
from backend.store import Store, make_message
from backend.visitors import MediaAccess
from backend.web_knowledge import KnowledgeStore
from tests.test_features import FakeMedia, ObservedEngine, context, decision, png
from tests.test_reasoning import FakeResearch


class Gateway:
    def __init__(self, callback=None):
        self.callback = callback or (lambda room, slot, prompt, cancel: decision(slot + " 的回答"))
        self.calls = []

    def room_status(self, room, assignments=None):
        return [{"id": p, "configured": True, "providerId": "gemini", "model": "gemini-4-argon"}
                for p in get_room(room)["characters"]]

    def respond_for(self, room, slot, prompt, cancel, **options):
        self.calls.append((room, slot, prompt))
        return self.callback(room, slot, prompt, cancel)


class WangshengEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "data")
        self.cid = self.store.create("wangsheng-trio", owner_id="a" * 64)["id"]
        self.media = MediaStore(self.root / "media")
        self.access = MediaAccess(self.root / "media-access.json")
        self.output = self.root / "generated.png"
        self.output.write_bytes(png())
        self.events = []

    def engine(self, callback=None, research=None, knowledge=None, codex=None, emit=None):
        gateway = Gateway(callback)
        engine = ObservedEngine(self.store, gateway, emit or (lambda e, p: self.events.append((e, p))),
            media=self.media, codex_media=codex or FakeMedia(self.output), research=research or FakeResearch(),
            knowledge=knowledge, media_access=self.access)
        self.addCleanup(engine.stop_all)
        return engine, gateway

    def finish(self, engine, text, settings=None, attachments=None, cid=None):
        identifier = cid or self.cid
        result = engine.start(identifier, text, {"maxRounds": 1, "webSearch": "off", **(settings or {})}, attachments=attachments)
        self.assertTrue(engine.wait_finished(result), result)
        return self.store.get(identifier)["messages"]

    def test_each_role_generates_from_shared_snapshot_even_with_fixed_room_order(self):
        order = get_room("wangsheng-trio")["turnOrder"]
        barrier = threading.Barrier(len(order))

        def respond(room, slot, prompt, cancel):
            replies = [m for m in context(prompt) if m["speaker"] in order]
            self.assertEqual(replies, [])
            durable = [m["provider"] for m in self.store.get(self.cid)["messages"] if m["role"] == "assistant"]
            self.assertEqual(durable, [])
            barrier.wait(timeout=2)
            return decision("实际回答-" + slot)

        engine, gateway = self.engine(respond)
        messages = self.finish(engine, "今天一起坐坐吧", {"participants": list(reversed(order))})
        self.assertEqual({call[1] for call in gateway.calls}, set(order))
        self.assertEqual({m["provider"] for m in messages if m["role"] == "assistant"}, set(order))

    def test_existing_rooms_share_parallel_snapshot_behavior(self):
        cid = self.store.create("zzz-trio")["id"]
        barrier = threading.Barrier(2)

        def respond(room, slot, prompt, cancel):
            self.assertEqual([m["speaker"] for m in context(prompt)], ["user"])
            barrier.wait(timeout=2)
            return decision(slot)

        engine, gateway = self.engine(respond)
        messages = self.finish(engine, "大家好", {"participants": ["deepseek", "gemini"]}, cid=cid)
        self.assertEqual({call[1] for call in gateway.calls}, {"deepseek", "gemini"})
        self.assertEqual(len([m for m in messages if m["role"] == "assistant"]), 2)

    def test_scene_commands_are_not_stored_as_dialogue_and_cancel_old_run(self):
        entered, release = threading.Event(), threading.Event()

        def blocked(room, slot, prompt, cancel):
            entered.set()
            release.wait(timeout=3)
            return decision("不应出现的旧场景回答")

        engine, gateway = self.engine(blocked)
        first = engine.start(self.cid, "请稍候", {"participants": ["deepseek"], "maxRounds": 1, "webSearch": "off"})
        self.assertTrue(entered.wait(2))
        result = engine.start(self.cid, "/私聊 钟离")
        self.assertEqual(result["command"]["type"], "scene")
        self.assertEqual(current_scene(result["conversation"])["audience"], ["user", "deepseek"])
        release.set()
        self.assertTrue(engine.wait_finished(first))
        contents = [m["content"] for m in self.store.get(self.cid)["messages"]]
        self.assertNotIn("/私聊 钟离", contents)
        self.assertNotIn("不应出现的旧场景回答", contents)

    def test_private_history_and_queries_do_not_reach_shared_research_or_absent_roles(self):
        research = FakeResearch()
        engine, gateway = self.engine(research=research)
        self.finish(engine, "/私聊 钟离 | PRIVATE_SECRET_123", {"participants": ["deepseek", "gemini"]})
        self.assertEqual([call[1] for call in gateway.calls], ["deepseek"])
        gateway.calls.clear()
        messages = self.finish(engine, "/全桌 | 帮我查一下公开名词", {"participants": ["deepseek", "gemini"], "webSearch": "auto"})
        self.assertEqual(len(research.calls), 1)
        self.assertNotIn("PRIVATE_SECRET_123", research.calls[0][0])
        by_slot = {call[1]: call[2] for call in gateway.calls}
        self.assertIn("PRIVATE_SECRET_123", by_slot["deepseek"])
        self.assertNotIn("PRIVATE_SECRET_123", by_slot["gemini"])
        self.assertFalse(any(m["content"].startswith("/全桌") for m in messages))
        scoped = shared_conversation(self.store.get(self.cid))
        self.assertEqual(_public_terms(scoped, ["PRIVATE_SECRET_123", "公开名词"]), ["公开名词"])

    def test_director_prompt_is_marked_and_not_addressed_as_present_user(self):
        def respond(room, slot, prompt, cancel):
            self.assertIn("旅行者不在场", prompt)
            self.assertTrue(any(m.get("director") and m["speaker"] == "director" for m in context(prompt)))
            return decision(slot)

        engine, gateway = self.engine(respond)
        messages = self.finish(engine, "/悄悄话 钟离 若娜瓦 | 两人坐下讨论晚饭")
        self.assertCountEqual([call[1] for call in gateway.calls], ["deepseek", "gpt"])
        self.assertTrue(next(m for m in messages if m["role"] == "user")["director"])
        for message in messages:
            if message["role"] == "assistant":
                self.assertEqual(message["replyTo"], "everyone")
                self.assertEqual(message["audience"], ["deepseek", "gpt"])

    def test_analysis_uses_only_shared_images_after_returning_to_table(self):
        codex = FakeMedia(self.output)
        engine, gateway = self.engine(codex=codex)
        secret = self.media.add(png(2, 3))
        public = self.media.add(png(3, 3))
        self.finish(engine, "/私聊 钟离 | PRIVATE_IMAGE_SECRET", attachments=[secret["id"]])
        codex.analysis_calls.clear()
        self.finish(engine, "/全桌 | 看看这张图片", attachments=[public["id"]])
        self.assertEqual(len(codex.analysis_calls), 1)
        paths, prompt, _ = codex.analysis_calls[0]
        self.assertEqual(paths, [self.media.path(public["id"])])
        self.assertNotIn("PRIVATE_IMAGE_SECRET", prompt)
        self.assertNotIn(secret["id"], prompt)

    def test_generation_remains_available_in_private_and_public_scenes(self):
        codex = FakeMedia(self.output)
        engine, gateway = self.engine(codex=codex)
        self.finish(engine, "/悄悄话 钟离 若娜瓦 | 生成两人的合影，不带我")
        private_prompt, paths, _ = codex.generation_calls[-1]
        self.assertIn("荧不在场", private_prompt)
        self.assertNotIn("user-avatar.png", [p.name for p in paths])
        self.assertEqual({p.name for p in paths}, {"wangsheng-deepseek-stand.png", "wangsheng-gpt-stand.png"})
        self.finish(engine, "/全桌 | 画一张兹白的头像")
        public_prompt, paths, _ = codex.generation_calls[-1]
        self.assertIn("银白色长发束成高马尾", public_prompt)
        self.assertEqual([p.name for p in paths], ["wangsheng-zibai.png"])
        self.assertNotIn("gpt-original.jpg", public_prompt)
        messages = self.store.get(self.cid)["messages"]
        images = [m for m in messages if m.get("kind") == "image"]
        self.assertEqual(len(images), 2)
        for message in images:
            for attachment in message["attachments"]:
                self.assertTrue(self.access.allowed(attachment["id"], "a" * 64))
                self.assertFalse(self.access.allowed(attachment["id"], "b" * 64))

    def test_media_ownership_exists_before_upload_or_generated_event(self):
        checked = []

        def emit(event, payload):
            if event == "message":
                for attachment in payload["message"].get("attachments", []):
                    self.assertFalse(self.access.allowed(attachment["id"], "b" * 64))
                    checked.append(attachment["id"])

        engine, gateway = self.engine(emit=emit)
        upload = self.media.add(png())
        self.finish(engine, "看看图片", attachments=[upload["id"]])
        self.finish(engine, "画一张钟离的头像")
        self.assertEqual(len(checked), 2)

    def test_local_knowledge_reuse_respects_off_always_owner_and_scene(self):
        knowledge = KnowledgeStore(self.root / "knowledge")
        source = {"title": "公开名词", "url": "https://www.python.org/"}
        seed = make_message("user", "公开名词", webResearch={"status": "complete", "summary": "SCOPED_EVIDENCE",
            "sources": [source], "checkedAt": "2026-10-16T00:00:00+00:00"},
            audience=current_scene(self.store.get(self.cid))["audience"])
        # Use actual current UTC for storage validity; the story clock is unrelated.
        from datetime import datetime, timezone
        seed["webResearch"]["checkedAt"] = datetime.now(timezone.utc).isoformat()
        knowledge.save(self.store.get(self.cid), seed)
        research = FakeResearch()
        engine, gateway = self.engine(research=research, knowledge=knowledge)
        messages = self.finish(engine, "公开名词是什么？", {"participants": ["deepseek"]})
        self.assertEqual(research.calls, [])
        user = next(m for m in reversed(messages) if m["role"] == "user")
        self.assertEqual(user["webResearch"]["origin"], "local")
        self.assertIn("SCOPED_EVIDENCE", gateway.calls[-1][2])
        self.assertNotIn(source["url"], gateway.calls[-1][2])
        self.finish(engine, "再聊聊公开名词", {"participants": ["deepseek"], "webSearch": "always"})
        self.assertEqual(len(research.calls), 1)
        other = self.store.create("wangsheng-trio", owner_id="b" * 64)["id"]
        messages = self.finish(engine, "公开名词", {"participants": ["deepseek"]}, cid=other)
        self.assertNotIn("webResearch", messages[0])

    def test_new_targets_and_default_prompt_still_supported(self):
        for slot in ("paimon", "xiangling", "xiao", "zibai"):
            self.assertEqual(parse_decision(json.dumps({"speak": True, "content": "你好", "to": slot}))["to"], slot)
        conversation = self.store.get(self.cid)
        conversation["messages"] = [make_message("user", "你好")]
        self.assertIn("钟离", build_prompt("deepseek", conversation, 1))


if __name__ == "__main__":
    unittest.main()
