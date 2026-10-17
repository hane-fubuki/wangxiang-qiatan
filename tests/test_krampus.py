import json
from pathlib import Path
import tempfile
import unittest

from backend.engine import _image_subjects, _image_context_subjects, build_prompt
from backend.krampus import CHARACTER_NAMES, ROOM_ID
from backend.rooms import get_room, is_mentioned, model_route
from backend.skills import SkillStore, parse_command
from backend.store import Store, default_settings
from backend.visual_skills import character_visual_reference


class KrampusTests(unittest.TestCase):
    def test_five_members_and_independent_models_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            conversation = store.create(room_id=ROOM_ID)
            self.assertEqual(conversation['settings']['participants'], list(CHARACTER_NAMES))
            settings = {'models': {'zhao': {'providerId': 'gpt', 'model': 'gpt-6.1-sol'}}}
            store.update(conversation['id'], {'settings': settings})
            loaded = Store(directory).get(conversation['id'])
            self.assertEqual(loaded['settings']['models'], settings['models'])
            for slot in CHARACTER_NAMES:
                self.assertEqual(model_route(ROOM_ID, slot), ('gemini', 'gemini-4-argon'))

    def test_names_do_not_match_photography_words(self):
        members = list(CHARACTER_NAMES)
        for prompt in ['给琉音拍照', '照着菲欧妮的照片画', '画普罗米娅，参考照片', '拍一张般岳的照片']:
            self.assertNotIn('zhao', _image_subjects(prompt, ROOM_ID, members)[1])
        for prompt in ['给照画个头像', '照和琉音的合影', '@照 穿青绿外套', '和照一起拍照']:
            self.assertIn('zhao', _image_subjects(prompt, ROOM_ID, members)[1])
        self.assertTrue(is_mentioned(ROOM_ID, 'zhao', '@小照'))
        self.assertTrue(is_mentioned(ROOM_ID, 'zhao', '@照 你好'))
        self.assertFalse(is_mentioned(ROOM_ID, 'zhao', '@照片'))
        self.assertFalse(is_mentioned('zzz-trio', 'gemini', '@琉音'))
        self.assertEqual(set(_image_subjects('黑枝全员合影', ROOM_ID, members)[1]), set(members))
        _, subjects = _image_context_subjects('照着她刚才的样子画', ROOM_ID, members,
            [{'role': 'user', 'content': '菲欧妮换了一件浅蓝外套'}])
        self.assertEqual(subjects, ['phoenix'])

    def test_skills_save_undo_reload_and_room_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            skills = SkillStore(directory)
            self.assertEqual({s['id'] for s in skills.list()}, {'gemini', 'deepseek', 'gpt', 'belle'})
            self.assertEqual([s['name'] for s in skills.list(ROOM_ID)], [*CHARACTER_NAMES.values(), '铃'])
            skills.update('dialyn', '今天话少一些', expected=0)
            restored = SkillStore(directory)
            self.assertEqual(restored.get('dialyn')['content'], '今天话少一些')
            self.assertEqual(restored.get('gemini')['content'], '')
            self.assertEqual(restored.undo('dialyn', expected=1)['content'], '')
            self.assertEqual(parse_command('/设定 照 多听一会儿', ROOM_ID)['id'], 'zhao')
            self.assertIsNone(parse_command('/设定 千夏 多听一会儿', ROOM_ID))
            for slot in CHARACTER_NAMES:
                self.assertTrue((Path(directory)/slot/'SKILL.md').is_file())

    def test_visual_assets_and_personality_reach_prompts(self):
        root = Path(__file__).resolve().parents[1]
        for slot, name in CHARACTER_NAMES.items():
            visual = character_visual_reference(slot, room_id=ROOM_ID)
            self.assertIn(name, visual['text'])
            self.assertTrue(Path(visual['referencePath']).is_file())
            for kind in ('stand', 'avatar'):
                self.assertTrue((root/'web'/get_room(ROOM_ID)['characters'][slot][kind].lstrip('/')).is_file())
            conversation = {'roomId': ROOM_ID, 'settings': default_settings(ROOM_ID), 'messages': []}
            prompt = build_prompt(slot, conversation, 1, False, 'USER_CUSTOM_MARKER')
            self.assertIn('你只扮演'+name, prompt)
            self.assertIn('USER_CUSTOM_MARKER', prompt)
            self.assertNotIn('你只扮演千夏', prompt)


if __name__ == '__main__':
    unittest.main()
