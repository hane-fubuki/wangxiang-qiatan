"""Protagonist control and participation exercised through the real chat engine."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from backend.engine import build_prompt
from backend import protagonists
from backend.rooms import get_room, public_rooms
from backend.skills import SkillStore, editable_ids, parse_command
from backend.store import Store, make_message, default_settings
from backend.scenes import visible_conversation, scene_instruction
from tests.test_features import ObservedEngine, context, decision
from tests.test_wangsheng_engine import Gateway


class ProtagonistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "history")

    def engine(self, callback=None):
        gateway = Gateway(callback)
        events = []
        engine = ObservedEngine(self.store, gateway, lambda e, p: events.append((e, p)))
        self.addCleanup(engine.stop_all)
        return engine, gateway, events

    def finish(self, engine, cid, text, **settings):
        result = engine.start(cid, text, {"webSearch": "off", "maxRounds": 1, **settings})
        self.assertTrue(engine.wait_finished(result))
        messages = self.store.get(cid)["messages"]
        self.assertFalse([m for m in messages if m.get("kind") == "error"], messages)
        return messages

    def test_room_scope_and_optional_seating_are_independent_of_default_user(self):
        for room in public_rooms():
            self.assertIn("belle", room["characters"])
            self.assertNotIn("lumine", room["characters"])
            self.assertEqual("lumine" in room["userCharacters"], room["id"] == "wangsheng-trio")
            settings = default_settings(room["id"])
            self.assertNotIn("belle", settings["participants"])
            self.assertNotIn("lumine", settings["participants"])
            self.assertEqual(settings["userRole"], "lumine" if room["id"] == "wangsheng-trio" else "self")

    def test_guest_throttling_and_explicit_invitation(self):
        cid = self.store.create()["id"]
        engine, gateway, _ = self.engine(lambda room, slot, prompt, cancel: decision(slot + str(len(context(prompt)))))
        self.finish(engine, cid, "大家随便聊聊", participants=["gemini", "belle"])
        self.assertEqual({call[1] for call in gateway.calls}, {"gemini", "belle"})
        gateway.calls.clear()
        self.finish(engine, cid, "我接着说一件小事")
        self.assertEqual([call[1] for call in gateway.calls], ["gemini"])
        gateway.calls.clear()
        self.finish(engine, cid, "@玲 你觉得呢？")
        self.assertEqual({call[1] for call in gateway.calls}, {"gemini", "belle"})

    def test_wangsheng_never_generates_an_ai_lumine(self):
        cid = self.store.create("wangsheng-trio")["id"]
        engine, gateway, _ = self.engine()
        self.finish(engine, cid, "大家聊聊今天的天气", participants=["gemini", "belle"], mode="all")
        self.assertEqual(len([c for c in gateway.calls if c[1] in protagonists.NAMES]), 1)
        gateway.calls.clear()
        self.finish(engine, cid, "荧和玲各说一句吧")
        self.assertEqual({c[1] for c in gateway.calls}, {"gemini", "belle"})
        self.assertIn("荧由用户独占扮演", gateway.calls[0][2])

    def test_human_control_excludes_duplicate_ai_and_does_not_relabel_old_messages(self):
        cid = self.store.create("wangsheng-trio")["id"]
        engine, gateway, _ = self.engine()
        self.finish(engine, cid, "我的旧身份内容", participants=["gemini"], userRole="self", interactionMode="chat")
        original = self.store.get(cid)["messages"][0]
        gateway.calls.clear()
        messages = self.finish(engine, cid, "这是荧由我说的话", participants=["gemini"], userRole="lumine", interactionMode="chat")
        self.assertEqual([c[1] for c in gateway.calls], ["gemini"])
        latest = self.store.get(cid)
        self.assertEqual(messages[0]["actor"], original["actor"])
        self.assertEqual(context(gateway.calls[0][2])[0]["speakerName"], "荧")
        self.assertNotIn("我的旧身份内容", gateway.calls[0][2])
        self.assertEqual(latest["settings"]["participants"], ["gemini"])
        self.assertTrue(all(m["identityEpoch"] == latest["identityEpoch"] for m in visible_conversation(latest, "gemini")["messages"]))

    def test_scene_mode_treats_input_as_direction_and_lets_belle_speak(self):
        cid = self.store.create()["id"]
        engine, gateway, _ = self.engine()
        messages = self.finish(engine, cid, "玲正看着桌上打不开的录像带盒", participants=["belle"], interactionMode="scene", userRole="self")
        self.assertTrue(messages[0]["director"])
        packed = context(gateway.calls[0][2])[0]
        self.assertEqual(packed["speaker"], "director")
        self.assertEqual(packed["actor"]["mode"], "scene")
        self.assertEqual(messages[-1]["provider"], "belle")
        self.assertEqual(messages[-1]["replyTo"], "everyone")

    def test_missing_guest_skill_isolated_from_other_models(self):
        cid = self.store.create()["id"]
        engine, gateway, _ = self.engine()
        with patch.object(protagonists, "DATA_ROOT", Path(self.temp.name) / "missing"):
            result = engine.start(cid, "玲请回应一下", {"participants": ["gemini", "belle"], "maxRounds": 1, "webSearch": "off"})
            self.assertTrue(engine.wait_finished(result))
        messages = self.store.get(cid)["messages"]
        self.assertTrue(any(m.get("provider") == "gemini" and m["role"] == "assistant" for m in messages))
        self.assertTrue(any(m.get("provider") == "belle" and m.get("kind") == "error" for m in messages))
        self.assertFalse(any(m.get("provider") == "belle" and m["role"] == "assistant" for m in messages))

    def test_editable_skill_scope_and_qa_are_portable(self):
        skills = SkillStore(Path(self.temp.name) / "skills")
        self.assertIn("belle", editable_ids("standard"))
        self.assertNotIn("lumine", editable_ids("standard"))
        self.assertEqual(parse_command("/设定 荧 回答简短一些", "wangsheng-trio")["id"], "lumine")
        self.assertIsNone(parse_command("/设定 荧 回答简短一些", "zzz-trio"))
        skills.update("belle", "本次小约定：先等对方说完。")
        self.assertIn("本次小约定", skills.prompt("belle"))
        for identifier in protagonists.NAMES:
            self.assertTrue(protagonists.read_document(identifier, "qa.md"))
            self.assertTrue(protagonists.read_document(identifier, "visual.md"))

    def test_skill_command_switches_identity_before_attributing_user_message(self):
        cid = self.store.create("wangsheng-trio")["id"]
        engine, gateway, _ = self.engine()
        engine.skills = SkillStore(Path(self.temp.name) / "skills")
        previous_epoch = self.store.get(cid)["identityEpoch"]
        result = engine.start(cid, "/设定 玲 简短自然一些", {"userRole": "belle", "interactionMode": "chat"})
        self.assertEqual(result["command"]["type"], "skill")
        chat = self.store.get(cid)
        self.assertNotEqual(chat["identityEpoch"], previous_epoch)
        self.assertEqual(chat["messages"][0]["actor"]["characterId"], "belle")
        self.assertEqual(chat["messages"][0]["actor"]["name"], "铃")
        self.assertEqual(gateway.calls, [])

    def test_unseated_guest_and_ordinary_words_do_not_invite_belle(self):
        chat = self.store.create("wangsheng-trio")
        self.assertNotIn("铃", scene_instruction(chat, "gemini"))
        chat = self.store.update(chat["id"], {"settings": {"participants": ["gemini", "belle"]}})
        self.assertIn("铃", scene_instruction(chat, "gemini"))
        from backend.rooms import character_named
        for ordinary in ("风铃", "铃声响了", "按铃", "门铃", "小巧玲珑"):
            for name in protagonists.ALIASES["belle"]:
                self.assertFalse(character_named(ordinary, name), (ordinary, name))


if __name__ == "__main__":
    unittest.main()
