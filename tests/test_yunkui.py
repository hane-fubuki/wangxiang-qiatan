import tempfile
import unittest
from pathlib import Path
from backend.yunkui import ROOM_ID, CHARACTER_NAMES
from backend.rooms import get_room, is_mentioned, model_route
from backend.skills import SkillStore, parse_command
from backend.store import Store, default_settings
from backend.engine import _image_subjects, build_prompt
from backend.scenes import parse_scene_command, visible_conversation
from backend.visual_skills import character_visual_reference

class YunkuiTests(unittest.TestCase):
    def test_room_model_and_settings_survive_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            c = store.create(room_id=ROOM_ID)
            self.assertEqual(c['settings']['participants'],list(CHARACTER_NAMES))
            models={'ye-shunguang':{'providerId':'gpt','model':'gpt-6.1-sol'}}
            store.update(c['id'],{'settings':{'models':models}})
            self.assertEqual(Store(directory).get(c['id'])['settings']['models'],models)
        self.assertEqual(get_room(ROOM_ID)['name'],'随便观顺便聊')
        for slot in CHARACTER_NAMES:
            self.assertEqual(model_route(ROOM_ID,slot),('gemini','gemini-4-argon'))

    def test_character_revisions_are_isolated_and_undoable(self):
        with tempfile.TemporaryDirectory() as directory:
            s=SkillStore(directory)
            self.assertEqual([x['name'] for x in s.list(ROOM_ID)],[*CHARACTER_NAMES.values(), '铃'])
            s.update('ye-shunguang','今天穿浅蓝外套',expected=0)
            s=SkillStore(directory)
            self.assertEqual(s.get('ye-shunguang')['content'],'今天穿浅蓝外套')
            self.assertEqual(s.get('gpt')['content'],'')
            self.assertEqual(s.undo('ye-shunguang',expected=1)['content'],'')
            self.assertEqual(parse_command('/设定 福福 说话短一些',ROOM_ID)['id'],'ju-fufu')
            self.assertIsNone(parse_command('/设定 千夏 说话短一些',ROOM_ID))

    def test_persona_visual_and_group_subjects(self):
        members=list(CHARACTER_NAMES)
        self.assertEqual(_image_subjects('云岿山全员合影',ROOM_ID,members),(False,members))
        self.assertEqual(_image_subjects('只给叶瞬光画头像',ROOM_ID,members),(False,['ye-shunguang']))
        self.assertTrue(is_mentioned(ROOM_ID,'ye-shunguang','@小光 你好'))
        for slot,name in CHARACTER_NAMES.items():
            visual=character_visual_reference(slot,room_id=ROOM_ID)
            self.assertTrue(Path(visual['referencePath']).is_file())
            c={'roomId':ROOM_ID,'settings':default_settings(ROOM_ID),'messages':[]}
            prompt=build_prompt(slot,c,1,False,'CUSTOM_YUNKUI_SETTING')
            self.assertIn('你只扮演'+name,prompt)
            self.assertIn('CUSTOM_YUNKUI_SETTING',prompt)
        self.assertIn('暖霞拾光',character_visual_reference('ye-shunguang',room_id=ROOM_ID)['text'])

    def test_private_scene_audience(self):
        scene,_=parse_scene_command('/私聊 仪玄 | 聊一会儿',ROOM_ID)
        c={'roomId':ROOM_ID,'messages':[{'role':'user','content':'秘密','audience':scene['audience']}]}
        self.assertEqual(len(visible_conversation(c,'yixuan')['messages']),1)
        self.assertEqual(visible_conversation(c,'ju-fufu')['messages'],[])

if __name__=='__main__': unittest.main()
