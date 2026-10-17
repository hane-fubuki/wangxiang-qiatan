"""Exercise identity, persistence, visibility and HTTP for the six-person room."""
import http.client
import tempfile
import threading
import unittest
from pathlib import Path

from app import create_server
from backend.outer_ring import ROOM_ID, CHARACTER_NAMES
from backend.engine import _image_subjects, build_prompt
from backend.rooms import get_room, model_route, is_mentioned
from backend.store import Store, default_settings
from backend.skills import SkillStore, parse_command
from backend.scenes import parse_scene_command, visible_conversation
from backend.visual_skills import character_visual_reference
from backend.remote_access import _route_allowed
from backend.starters import StarterGenerator, _ANGLES


class OfflineGateway:
    def status(self):
        return []


class OuterRingTests(unittest.TestCase):
    def test_six_identities_persist_with_independent_model_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            c = store.create(room_id=ROOM_ID)
            self.assertEqual(c['settings']['participants'], list(CHARACTER_NAMES))
            chosen = {'burnice': {'providerId':'gpt', 'model':'gpt-6.1-sol'}}
            store.update(c['id'], {'settings': {'models': chosen}})
            loaded = Store(directory).get(c['id'])
            self.assertEqual(loaded['settings']['models'], chosen)
            self.assertEqual(loaded['roomId'], ROOM_ID)
        self.assertEqual(get_room(ROOM_ID)['name'], '相亲相爱一家人')
        self.assertEqual(get_room(ROOM_ID)['groupName'], '外环')
        self.assertEqual(model_route(ROOM_ID,'lucy'), ('gemini','gemini-4-argon'))

    def test_alias_and_revision_survive_reload_without_leaking(self):
        self.assertTrue(is_mentioned(ROOM_ID, 'burnice', '@伯尼斯 今天喝什么'))
        self.assertEqual(parse_command('/设定 伯尼斯 今天穿白外套', ROOM_ID)['id'],'burnice')
        self.assertIsNone(parse_command('/设定 千夏 今天穿白外套', ROOM_ID))
        with tempfile.TemporaryDirectory() as directory:
            skills = SkillStore(directory)
            skills.update('burnice','今天穿白外套',expected=0)
            skills = SkillStore(directory)
            self.assertEqual(skills.get('burnice')['content'],'今天穿白外套')
            self.assertEqual(skills.get('piper')['content'],'')
            self.assertEqual(skills.get('gpt')['content'],'')
            self.assertEqual([s['id'] for s in skills.list(ROOM_ID)],[*CHARACTER_NAMES, 'belle'])
            self.assertEqual(skills.undo('burnice',expected=1)['content'],'')

    def test_prompt_image_identity_and_private_conversation(self):
        for slot,name in CHARACTER_NAMES.items():
            visual = character_visual_reference(slot,room_id=ROOM_ID)
            self.assertTrue(Path(visual['referencePath']).is_file())
            self.assertIn(name,visual['text'])
            c={'roomId':ROOM_ID,'settings':default_settings(ROOM_ID),'messages':[]}
            prompt=build_prompt(slot,c,1,False,'USER_CUSTOM_SETTING')
            self.assertIn('你只扮演'+name,prompt)
            self.assertIn('USER_CUSTOM_SETTING',prompt)
        scene,_=parse_scene_command('/私聊 伯尼斯 | 今天的秘密',ROOM_ID)
        c={'roomId':ROOM_ID,'messages':[{'role':'user','content':'秘密','audience':scene['audience']}]}
        self.assertEqual(len(visible_conversation(c,'burnice')['messages']),1)
        self.assertEqual(visible_conversation(c,'lucy')['messages'],[])
        self.assertEqual(_image_subjects('外环全员合影',ROOM_ID,list(CHARACTER_NAMES)),(False,list(CHARACTER_NAMES)))
        self.assertEqual(_image_subjects('给伯尼斯画头像',ROOM_ID,list(CHARACTER_NAMES)),(False,['burnice']))

    def test_starter_uses_the_correct_people(self):
        room=get_room(ROOM_ID)
        for starter in room['starters']:
            prompt=StarterGenerator._prompt(room,starter,_ANGLES[(ROOM_ID,starter['id'])][0],[])
            self.assertIn('柏妮思、凯撒、露西、莱特、波可娜、派派',prompt)

    def test_static_routes_available_and_reference_files_private(self):
        with tempfile.TemporaryDirectory() as directory:
            server=create_server(port=0,data_dir=directory,gateway=OfflineGateway())
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                routes=['/outer-ring-theme.css','/outer-ring-icons.js']+[
                    f'/assets/outer-ring-{slot}-{kind}.png' for slot in CHARACTER_NAMES for kind in ('stand','avatar')]
                for path in routes:
                    self.assertTrue(_route_allowed('GET',path),path)
                    connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                    connection.request('GET',path); response=connection.getresponse()
                    self.assertEqual(response.status,200,path)
                    self.assertTrue(response.read());connection.close()
                path='/resources/outer-ring/characters/burnice.md'
                self.assertFalse(_route_allowed('GET',path))
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                connection.request('GET',path); response=connection.getresponse()
                self.assertEqual(response.status,404);response.read();connection.close()
            finally:
                server.engine.stop_all();server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':
    unittest.main()
