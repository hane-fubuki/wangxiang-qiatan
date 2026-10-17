"""The shared writing layer must never replace room identity or visibility."""
import copy
import unittest
from unittest.mock import patch

from backend.dialogue_style import dialogue_style_instruction
from backend.engine import build_prompt
from backend.reasoning import research_instruction
from backend.rooms import get_room, persona_prompt, public_rooms
from backend.store import default_settings, make_message


class DialogueStyleTests(unittest.TestCase):
    def conversation(self, room_id):
        return {"roomId": room_id, "settings": default_settings(room_id),
                "messages": [make_message("user", "先坐一会儿吧，今天不想赶着去哪。")]}

    def test_all_current_characters_keep_personas_and_receive_one_shared_layer(self):
        style = dialogue_style_instruction()
        for room in public_rooms():
            for slot in room["characters"]:
                with self.subTest(room=room["id"], slot=slot):
                    prompt = build_prompt(slot, self.conversation(room["id"]), 1)
                    self.assertEqual(prompt.count(style), 1)
                    self.assertIn(persona_prompt(room["id"], slot), prompt)
                    self.assertIn("只代表自己发言", prompt)
                    self.assertIn("不每句添加括号动作", prompt)
                    self.assertIn("并非每轮都要推动剧情", prompt)

    def test_future_room_inherits_style_without_being_added_to_an_allowlist(self):
        from backend import rooms
        future = copy.deepcopy(get_room("zzz-trio"))
        future.update(id="future-dialogue-room", name="未来房间")
        with patch.dict(rooms._ROOMS, {future["id"]: future}):
            prompt = build_prompt("gemini", self.conversation(future["id"]), 1)
            self.assertEqual(prompt.count(dialogue_style_instruction()), 1)
            self.assertIn("只扮演千夏", prompt)

    def test_style_is_not_inserted_into_reference_data_used_for_images(self):
        for room in public_rooms():
            for slot in room["characters"]:
                with self.subTest(room=room["id"], slot=slot):
                    self.assertNotIn(dialogue_style_instruction(), persona_prompt(room["id"], slot))

    def test_research_does_not_expand_character_knowledge_or_claim_recollections(self):
        conversation = self.conversation("wangsheng-trio")
        conversation["messages"][0]["webResearch"] = {"status": "complete", "summary": "公开事实"}
        rule = research_instruction(conversation)
        self.assertIn("不等于角色亲历的记忆", rule)
        self.assertIn("知情边界", rule)
        self.assertIn("不可编造设定或声称已核实", rule)


if __name__ == "__main__":
    unittest.main()
