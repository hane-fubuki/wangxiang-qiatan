"""Exercise the new room through storage, routing, visibility and HTTP boundaries."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from app import create_server
from backend.engine import _image_subjects, build_prompt
from backend.roscaelifer import ROOM_ID, CHARACTER_NAMES, read_document
from backend.rooms import get_room, is_mentioned, model_route
from backend.remote_access import _route_allowed
from backend.scenes import parse_scene_command, visible_conversation
from backend.skills import SkillStore, parse_command
from backend.starters import StarterGenerator, _ANGLES
from backend.store import Store, default_settings
from backend.visual_skills import character_visual_reference


class OfflineGateway:
    def status(self):
        return []


class RoscaeliferTests(unittest.TestCase):
    def test_room_persistence_and_independent_model_assignment(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            conversation = store.create(room_id=ROOM_ID)
            self.assertEqual(conversation['settings']['participants'], list(CHARACTER_NAMES))
            models = {'velina': {'providerId':'gpt', 'model':'gpt-6.1-sol'}}
            store.update(conversation['id'], {'settings': {'models':models}})
            loaded = Store(directory).get(conversation['id'])
            self.assertEqual(loaded['roomId'], ROOM_ID)
            self.assertEqual(loaded['settings']['models'], models)
        self.assertEqual(get_room(ROOM_ID)['name'], '天空之城')
        self.assertEqual(get_room(ROOM_ID)['groupName'], '罗斯凯利法')
        self.assertEqual(model_route(ROOM_ID, 'norma'), ('gemini','gemini-4-argon'))
        self.assertEqual(get_room('zzz-mockingbird')['name'], '法厄同一生推')
        self.assertIn('非官方', get_room(ROOM_ID)['characters']['lindverne']['artNote'])

    def test_skill_revisions_reload_without_affecting_partner_or_other_rooms(self):
        with tempfile.TemporaryDirectory() as directory:
            skills = SkillStore(directory)
            skills.update('norma', '今天换上浅蓝外套', expected=0)
            skills = SkillStore(directory)
            self.assertEqual(skills.get('norma')['content'], '今天换上浅蓝外套')
            self.assertEqual(skills.get('velina')['content'], '')
            self.assertEqual(skills.get('gpt')['content'], '')
            self.assertEqual([s['id'] for s in skills.list(ROOM_ID)], [*CHARACTER_NAMES, 'belle'])
            self.assertEqual(skills.undo('norma', expected=1)['content'], '')
        self.assertEqual(parse_command('/设定 诺姆 说话短一些', ROOM_ID)['id'], 'norma')
        self.assertEqual(parse_command('/撤销设定 Velina', ROOM_ID)['id'], 'velina')
        self.assertIsNone(parse_command('/设定 千夏 说话短一些', ROOM_ID))

    def test_prompt_and_visual_identity_are_attached_to_correct_slots(self):
        for slot, name in CHARACTER_NAMES.items():
            visual = character_visual_reference(slot, room_id=ROOM_ID)
            self.assertTrue(Path(visual['referencePath']).is_file())
            if slot == 'lindverne':
                self.assertEqual(Path(visual['referencePath']).name, 'lindverne-model-full.png')
            self.assertIn(name, visual['text'])
            conversation = {'roomId':ROOM_ID,'settings':default_settings(ROOM_ID),'messages':[]}
            prompt = build_prompt(slot, conversation, 1, False, 'CUSTOM_ROSCAELIFER_SETTING')
            self.assertIn('你只扮演'+name, prompt)
            self.assertIn('CUSTOM_ROSCAELIFER_SETTING', prompt)
            self.assertTrue(is_mentioned(ROOM_ID, slot, '@'+name+' 你好'))
        with self.assertRaises(ValueError):
            read_document('../velina', 'visual')

    def test_photo_selection_and_private_audience(self):
        members = list(CHARACTER_NAMES)
        self.assertEqual(_image_subjects('罗斯凯利法全员合影', ROOM_ID, members), (False, members))
        self.assertEqual(_image_subjects('只给维琳娜画头像', ROOM_ID, members), (False, ['velina']))
        scene, _ = parse_scene_command('/私聊 诺姆 | 说个秘密', ROOM_ID)
        conversation = {'roomId':ROOM_ID, 'messages':[{'role':'user','content':'秘密','audience':scene['audience']}]}
        self.assertEqual(len(visible_conversation(conversation,'norma')['messages']), 1)
        self.assertEqual(visible_conversation(conversation,'velina')['messages'], [])

    def test_starter_generation_context_is_room_specific(self):
        room = get_room(ROOM_ID)
        for starter in room['starters']:
            angles = _ANGLES[(ROOM_ID, starter['id'])]
            self.assertTrue(angles)
            prompt = StarterGenerator._prompt(room, starter, angles[0], [])
            self.assertIn('诺姆、维琳娜、希格莉德、克拉蕾、洛克茜、林德薇恩', prompt)
            self.assertIn('不凭群名假定用户就是法厄同', prompt)

    def test_http_serves_new_theme_and_images_but_not_reference_data(self):
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(port=0, data_dir=directory, gateway=OfflineGateway())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for path in ['/roscaelifer-theme.css', '/roscaelifer-icons.js'] + [
                        f'/assets/roscaelifer-{slot}-{kind}.png'
                        for slot in CHARACTER_NAMES for kind in ('stand','avatar')]:
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=4)
                    connection.request('GET', path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, path)
                    self.assertTrue(response.read())
                    connection.close()
                for slot in CHARACTER_NAMES:
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=4)
                    connection.request('POST', '/api/skills/'+slot,
                                       json.dumps({'content':'测试：'+slot, 'expectedVersion':0}),
                                       {'Content-Type':'application/json'})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, slot)
                    self.assertEqual(json.loads(response.read())['version'], 1)
                    connection.close()
                self.assertEqual(server.skills.get('vivian')['content'], '')
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=4)
                connection.request('GET', '/resources/roscaelifer/characters/norma.md')
                response = connection.getresponse()
                self.assertEqual(response.status, 404)
                response.read()
                connection.close()
            finally:
                server.engine.stop_all()
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_remote_allowlist_keeps_character_assets_and_settings_bounded(self):
        for path in ('/roscaelifer-theme.css', '/roscaelifer-icons.js',
                     '/assets/roscaelifer-norma-avatar.png', '/assets/roscaelifer-velina-stand.png'):
            self.assertTrue(_route_allowed('GET', path), path)
        for path in [f'/api/skills/{slot}{suffix}' for slot in CHARACTER_NAMES for suffix in ('','/undo')]:
            self.assertTrue(_route_allowed('POST', path), path)
        for path in ('/assets/roscaelifer-norma-intro.png', '/assets/roscaelifer-unknown-avatar.png',
                     '/resources/roscaelifer/characters/norma.md', '/roscaelifer-icons.js.bak'):
            self.assertFalse(_route_allowed('GET', path), path)


if __name__ == '__main__':
    unittest.main()
