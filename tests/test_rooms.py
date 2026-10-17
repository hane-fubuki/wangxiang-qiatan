"""Room persistence and prompt isolation across model-owned character turns."""
import json
from pathlib import Path
import tempfile
import threading
import unittest

from backend.engine import Engine, build_prompt
from backend.rooms import get_room, is_mentioned, model_route, persona_prompt, public_rooms, validate_room
from backend.store import Store, make_message
from tests.test_features import ObservedEngine


def conversation_data(prompt):
    return json.loads(prompt.split("<conversation_data>\n", 1)[1].split("\n</conversation_data>", 1)[0])


class RoomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def test_public_catalog_prioritizes_trio_and_adds_grok_without_private_profiles(self):
        rooms = public_rooms()
        self.assertEqual([room["id"] for room in rooms], ["zzz-trio", "zzz-roscaelifer", "zzz-outer-ring", "zzz-mockingbird", "wangsheng-trio", "zzz-yunkui", "zzz-obol", "zzz-krampus", "standard"])
        trio = rooms[0]
        self.assertGreater(trio["priority"], rooms[1]["priority"])
        standard = next(room for room in rooms if room["id"] == "standard")
        self.assertEqual(set(standard["characters"]), {"deepseek", "gemini", "gpt", "grok", "belle"})
        self.assertEqual(standard["characters"]["grok"]["name"], "Grok")
        self.assertEqual(trio["name"], "妄想茶话会")
        self.assertEqual(trio["category"], "酒馆")
        expected = {"gemini": ("千夏", "Gemini", "sunna"), "deepseek": ("南宫羽", "Gemini 4 Argon", "nangong-yu"),
                    "gpt": ("爱芮", "GPT", "aria")}
        for provider, (name, model, asset) in expected.items():
            character = {"name": name, "modelName": model,
                         "stand": f"/assets/zzz-{asset}-stand.png", "avatar": f"/assets/zzz-{asset}-avatar.png"}
            if provider in {"gemini", "deepseek"}:
                character.update(providerId="gemini", model="gemini-3.8-flash" if provider == "gemini" else "gemini-4-argon")
            self.assertEqual(trio["characters"][provider], character)
        self.assertTrue(all(set(starter) == {"id", "icon", "title", "description"} for starter in trio["starters"]))
        text = json.dumps(rooms, ensure_ascii=False)
        for private in ("persona", "_PERSONA_SOURCES", "你只扮演", "SKILL.md", "references/", "C:\\Users"):
            self.assertNotIn(private, text)
        rooms[0]["characters"]["gpt"]["name"] = "改动"
        self.assertEqual(get_room("zzz-trio")["characters"]["gpt"]["name"], "爱芮")

    def test_room_model_routes_preserve_character_slots_and_standard_defaults(self):
        self.assertEqual(model_route("zzz-trio", "deepseek"), ("gemini", "gemini-4-argon"))
        self.assertEqual(model_route("zzz-trio", "gemini"), ("gemini", "gemini-3.8-flash"))
        self.assertEqual(model_route("zzz-trio", "gpt"), ("gpt", None))
        for slot in ("deepseek", "gemini", "gpt", "grok"):
            self.assertEqual(model_route("standard", slot), (slot, None))
        for room, slot in (("missing", "deepseek"), ("zzz-trio", "missing"), ("zzz-trio", None), ("zzz-trio", [])):
            with self.subTest(room=room, slot=slot), self.assertRaises(ValueError):
                model_route(room, slot)

    def test_nangong_persona_keeps_identity_independent_of_selected_model(self):
        prompt = persona_prompt("zzz-trio", "deepseek")
        self.assertIn("deepseek=南宫羽", prompt)
        self.assertNotIn("Gemini 4 Argon", prompt)
        self.assertIn("用户可以独立选择每位角色使用的模型", prompt)
        self.assertNotIn("DeepSeek", prompt)
        self.assertIn("你只扮演南宫羽", prompt)
        self.assertIn("角色路由标识 gemini、deepseek、gpt", prompt)

    def test_legacy_history_defaults_to_standard_without_rewriting_source(self):
        original = self.store.create()
        original.pop("roomId")
        original["messages"].append(make_message("user", "旧聊天记录"))
        path = Path(self.temp.name) / "conversations.json"
        payload = json.dumps({"version": 1, "conversations": [original]}, ensure_ascii=False)
        path.write_text(payload, encoding="utf-8")
        restored = Store(self.temp.name)
        self.assertEqual(restored.get(original["id"])["roomId"], "standard")
        self.assertEqual(restored.list()[0]["messages"], original["messages"])
        self.assertEqual(path.read_text(encoding="utf-8"), payload)
        restored.update(original["id"], {"title": "更新旧聊天"})
        self.assertEqual(Store(self.temp.name).get(original["id"])["roomId"], "standard")

    def test_room_persists_and_cannot_be_changed_atomically(self):
        trio = self.store.create("zzz-trio")
        self.assertEqual(Store(self.temp.name).get(trio["id"])["roomId"], "zzz-trio")
        with self.assertRaisesRegex(ValueError, "不能更换"):
            self.store.update(trio["id"], {"roomId": "standard", "title": "不应该改变", "settings": {"maxRounds": 8}})
        self.assertEqual(self.store.get(trio["id"]), trio)
        self.assertEqual(Store(self.temp.name).get(trio["id"]), trio)
        self.assertEqual(self.store.update(trio["id"], {"roomId": "zzz-trio"})["roomId"], "zzz-trio")

    def test_invalid_room_cannot_create_or_change_history(self):
        standard = self.store.create()
        for invalid in ("unknown", "", None, [], {}, 1):
            with self.subTest(room=invalid):
                with self.assertRaises(ValueError):
                    validate_room(invalid)
                with self.assertRaises(ValueError):
                    self.store.create(invalid)
                with self.assertRaises(ValueError):
                    self.store.update(standard["id"], {"roomId": invalid, "title": "不应该改变"})
        self.assertEqual(self.store.list(), [standard])

    def test_character_and_provider_mentions_work_without_chinese_word_boundary(self):
        examples = (("gemini", "@千夏你觉得呢"), ("deepseek", "@南宫 你好"), ("deepseek", "@南宫羽，请接着说"),
                    ("gpt", "@爱芮也来聊聊"), ("gpt", "@GPT请回答"), ("gemini", "@Gemini 你好"),
                    ("deepseek", "@deepseek：请回应"))
        for provider, text in examples:
            with self.subTest(text=text):
                self.assertTrue(is_mentioned("zzz-trio", provider, text))
                for other in ("deepseek", "gemini", "gpt"):
                    if other != provider:
                        self.assertFalse(is_mentioned("zzz-trio", other, text))
        self.assertFalse(is_mentioned("standard", "gpt", "@爱芮 你好"))
        self.assertFalse(is_mentioned("zzz-trio", "gpt", "@gpt_extra 你好"))
        self.assertFalse(is_mentioned("zzz-trio", "gpt", "联系 person@gpt.example"))

    def test_persona_is_independent_from_standard_room_and_other_characters(self):
        standard = self.store.create()
        trio = self.store.create("zzz-trio")
        for provider, name in (("gemini", "千夏"), ("deepseek", "南宫羽"), ("gpt", "爱芮")):
            with self.subTest(provider=provider):
                standard_prompt = build_prompt(provider, standard, 1)
                trio_prompt = build_prompt(provider, trio, 1)
                self.assertIn("你只扮演" + name, trio_prompt)
                self.assertIn("休息室", trio_prompt)
                self.assertIn("用户默认是来到这里聊天的朋友", trio_prompt)
                self.assertNotIn("你只扮演" + name, standard_prompt)
                self.assertNotIn("千夏", standard_prompt)
                self.assertNotIn("鲸娘", trio_prompt)
                self.assertNotIn("白龙娘", trio_prompt)
                self.assertNotIn("A-H0L0", trio_prompt)
                self.assertNotIn("虚拟投影", trio_prompt)
        self.assertIn("音乐创作", build_prompt("gemini", trio, 1))
        self.assertIn("队长与编舞", build_prompt("deepseek", trio, 1))
        self.assertIn("主唱", build_prompt("gpt", trio, 1))

    def test_only_latest_user_mention_requires_first_round_reply(self):
        trio = self.store.create("zzz-trio")
        self.store.append(trio["id"], make_message("user", "@爱芮说说看"))
        self.store.append(trio["id"], make_message("assistant", "@南宫羽继续吧", provider="gpt"))
        trio = self.store.get(trio["id"])
        required = "本轮是否要求你回应用户：是"
        self.assertIn(required, build_prompt("gpt", trio, 1))
        self.assertNotIn(required, build_prompt("deepseek", trio, 1))
        self.assertNotIn(required, build_prompt("gpt", trio, 2))
        self.assertNotIn(required, build_prompt("gpt", trio, 1, continued=True))
        trio = self.store.append(trio["id"], make_message("user", "大家可以自由聊"))
        self.assertNotIn(required, build_prompt("gpt", trio, 1))

    def test_character_rounds_keep_provider_routing_and_share_only_this_room_history(self):
        trio = self.store.create("zzz-trio")
        standard = self.store.create()
        self.store.append(standard["id"], make_message("user", "标准房的私有历史不应进入角色房"))
        barrier = threading.Barrier(3)
        calls = []
        lock = threading.Lock()
        finished = threading.Event()
        names = {"gemini": "千夏", "deepseek": "南宫羽", "gpt": "爱芮"}
        targets = {"gemini": "deepseek", "deepseek": "gpt", "gpt": "gemini"}

        class Gateway:
            def status(self):
                return [{"id": provider, "configured": True} for provider in names]

            def respond(self, provider, prompt, cancel):
                with lock:
                    number = 1 + sum(call[0] == provider for call in calls)
                    calls.append((provider, prompt))
                if number == 1:
                    barrier.wait(timeout=2)
                    return json.dumps({"speak": True, "to": targets[provider], "content": names[provider] + "的回复"})
                return '{"speak":false,"to":"everyone","content":""}'

        def emit(event, payload):
            if event == "state" and payload["status"] == "idle":
                finished.set()

        engine = ObservedEngine(self.store, Gateway(), emit)
        self.addCleanup(engine.stop_all)
        engine.start(trio["id"], "三位聊聊新歌")
        self.assertTrue(finished.wait(4))
        self.assertEqual(len(calls), 6)
        for _, prompt in calls[:3]:
            self.assertEqual([m["speaker"] for m in conversation_data(prompt)], ["user"])
        for provider, prompt in calls:
            self.assertNotIn("标准房的私有历史", prompt)
            self.assertIn("你只扮演" + names[provider], prompt)
        for _, prompt in calls[3:]:
            messages = conversation_data(prompt)
            self.assertEqual({m["speaker"]: m["speakerName"] for m in messages}, {"user": "你", **names})
            self.assertEqual({m["speaker"]: m["to"] for m in messages if m["speaker"] != "user"}, targets)
        replies = [m for m in self.store.get(trio["id"])["messages"] if m["role"] == "assistant"]
        self.assertEqual(len(replies), 3)
        self.assertEqual({m["provider"]: m["replyTo"] for m in replies}, targets)
        self.assertEqual(len(self.store.get(standard["id"])["messages"]), 1)


if __name__ == "__main__":
    unittest.main()
