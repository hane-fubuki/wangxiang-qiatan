import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.lore import lore_prompt
from backend.rooms import get_room, is_mentioned, model_route, persona_prompt, public_rooms, speaker_name
from backend.starters import StarterGenerator
from backend.visual_skills import character_visual_reference
from backend.wangsheng import CHARACTER_NAMES, DATA_ROOT, TURN_ORDER, read_document


class WangshengRoomTests(unittest.TestCase):
    def test_room_is_additive_and_trio_keeps_priority(self):
        rooms = public_rooms()
        self.assertEqual([room["id"] for room in rooms], ["zzz-trio", "zzz-roscaelifer", "zzz-outer-ring", "zzz-mockingbird", "wangsheng-trio", "zzz-yunkui", "zzz-obol", "zzz-krampus", "standard"])
        self.assertEqual(get_room("zzz-trio")["characters"]["gemini"]["name"], "千夏")
        self.assertEqual(get_room()["id"], "standard")
        room = get_room("wangsheng-trio")
        self.assertEqual(room["turnOrder"], list(TURN_ORDER))
        self.assertEqual(set(room["characters"]), set(CHARACTER_NAMES) | {"belle"})
        for slot in CHARACTER_NAMES:
            self.assertEqual(model_route("wangsheng-trio", slot), ("gemini", "gemini-4-argon"))
        self.assertEqual(speaker_name("wangsheng-trio", "user"), "用户")
        self.assertNotIn("user-avatar", json.dumps(room))
        room["characters"]["gpt"]["name"] = "changed"
        self.assertEqual(get_room("wangsheng-trio")["characters"]["gpt"]["name"], "若娜瓦")

    def test_imported_portraits_are_used_instead_of_legacy_svg_nameplates(self):
        room = get_room("wangsheng-trio")
        for slot in ("paimon", "xiangling", "xiao", "zibai"):
            self.assertNotIn("portraitPlaceholder", room["characters"][slot])
            self.assertEqual(room["characters"][slot]["stand"], f"/assets/wangsheng-{slot}.png")
            self.assertEqual(room["characters"][slot]["avatar"], f"/assets/wangsheng-{slot}.png")

    def test_aliases_do_not_leak_across_rooms(self):
        self.assertTrue(is_mentioned("wangsheng-trio", "deepseek", "@摩拉克斯 过来聊聊"))
        self.assertTrue(is_mentioned("wangsheng-trio", "gpt", "@小瓦 今天怎么样"))
        self.assertTrue(is_mentioned("wangsheng-trio", "xiao", "@降魔大圣"))
        self.assertFalse(is_mentioned("zzz-trio", "deepseek", "@钟离"))
        self.assertFalse(is_mentioned("wangsheng-trio", "deepseek", "@南宫羽"))

    def test_personas_are_isolated_and_keep_knowledge_boundaries(self):
        for slot, name in CHARACTER_NAMES.items():
            prompt = persona_prompt("wangsheng-trio", slot)
            self.assertIn(f"你只扮演{name}", prompt)
            self.assertIn("M06/M07", prompt)
            self.assertIn("未认可", prompt)
            self.assertIn("角色标识固定", prompt)
            self.assertIn("不是官方", prompt.replace("不声称为官方", "不是官方"))
            self.assertNotIn("千夏", prompt)
            self.assertNotIn("资料基础：", prompt)
            self.assertNotIn("有一次，来人把同一句话说了好几遍", prompt)
            self.assertNotIn("有一回，我把一份记录写得太简略", prompt)
        self.assertIn("千夏", persona_prompt("zzz-trio", "gemini"))
        self.assertNotIn("往生堂", persona_prompt("zzz-trio", "gemini"))
        with self.assertRaises(ValueError):
            persona_prompt("wangsheng-trio", "../secret")

    def test_persona_reads_current_local_data_without_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "characters").mkdir()
            (root / "relationships.md").write_text("关系甲", encoding="utf-8")
            profile = root / "characters" / "gemini.md"
            profile.write_text("角色初版", encoding="utf-8")
            with patch("backend.wangsheng.DATA_ROOT", root):
                self.assertIn("角色初版", persona_prompt("wangsheng-trio", "gemini"))
                profile.write_text("角色修改版", encoding="utf-8")
                current = persona_prompt("wangsheng-trio", "gemini")
                self.assertIn("角色修改版", current)
                self.assertNotIn("角色初版", current)

    def test_document_paths_and_sizes_are_bounded(self):
        for path in ("../rooms.py", str(Path(__file__).resolve()), "missing.md"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                read_document(path)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "large.md").write_bytes(b"a" * (65536 + 1))
            with patch("backend.wangsheng.DATA_ROOT", root), self.assertRaises(ValueError):
                read_document("large.md")

    def test_lore_only_uses_given_visible_history_and_correct_room(self):
        message = {"role": "user", "content": "逐月节里蓝君明的故事是什么？"}
        self.assertEqual(lore_prompt("zzz-trio", [message]), "")
        self.assertEqual(lore_prompt("wangsheng-trio", [{"content": "晚上吃什么"}]), "")
        text = lore_prompt("wangsheng-trio", [message])
        self.assertIn("蓝君明", text)
        self.assertIn("不是当前访客的亲历记忆", text)
        self.assertNotIn("神之眼由若娜瓦", text)
        self.assertIn("神之眼", lore_prompt("wangsheng-trio", [{"content": "胡桃的神之眼是谁赠予的？"}]))
        old_history = [message] + [{"content": "喝茶"}] * 12
        self.assertEqual(lore_prompt("wangsheng-trio", old_history), "")

    def test_visuals_never_reuse_trio_or_placeholder_art(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "backend").mkdir()
            assets = root / "web" / "assets"
            assets.mkdir(parents=True)
            for slot in CHARACTER_NAMES:
                (assets / f"wangsheng-{slot}-stand.png").write_bytes(b"\x89PNG\r\n\x1a\nexample")
                (assets / f"wangsheng-{slot}.png").write_bytes(b"\x89PNG\r\n\x1a\nnameplate")
            with patch("backend.visual_skills.__file__", str(root / "backend" / "visual_skills.py")):
                for slot, name in CHARACTER_NAMES.items():
                    visual = character_visual_reference(slot, room_id="wangsheng-trio")
                    self.assertIn(name, visual["text"])
                    self.assertNotIn("zzz-trio-reference", visual["source"])
                    if slot in ("deepseek", "gemini", "gpt"):
                        self.assertEqual(Path(visual["referencePath"]).name, f"wangsheng-{slot}-stand.png")
                    else:
                        self.assertEqual(Path(visual["referencePath"]).name, f"wangsheng-{slot}.png")
                        self.assertIn("近景" if slot in ("paimon", "xiangling") else "半身", visual["text"])
        self.assertIn("千夏", character_visual_reference("gemini")["text"])
        with self.assertRaises(ValueError):
            character_visual_reference("paimon")
        with self.assertRaises(ValueError):
            character_visual_reference("gemini", room_id="missing")

    def test_new_starters_generate_in_room_without_role_dialogue(self):
        text = "我路过璃月港时看见有人把旧茶杯仔细包好，说是想带回家留作纪念。忽然有点好奇，同样是一件日常小物，为什么有的会让人舍不得丢，有的却能痛快放下？今天不赶时间，想听听大家各自会怎样看待，也可以从一顿饭或者一段路说起。"

        class Gateway:
            def __init__(self):
                self.prompts = []
            def status(self):
                return [{"id": "gemini", "configured": True}]
            def respond(self, provider, prompt, cancel):
                self.prompts.append(prompt)
                return json.dumps({"speak": True, "to": "everyone", "content": text}, ensure_ascii=False)

        gateway = Gateway()
        generator = StarterGenerator(gateway)
        for starter in get_room("wangsheng-trio")["starters"]:
            self.assertEqual(generator.generate("wangsheng-trio", starter["id"])["prompt"], text)
        for prompt in gateway.prompts:
            self.assertIn("钟离、胡桃、若娜瓦、香菱、魈、兹白、派蒙", prompt)
            self.assertNotIn("千夏", prompt)
            self.assertNotIn("舞台灯光", prompt)
        with self.assertRaises(ValueError):
            generator._content(json.dumps({"speak": True, "to": "everyone", "content": "派蒙：" + text}))


if __name__ == "__main__":
    unittest.main()
