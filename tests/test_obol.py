"""404 roster and identity boundaries across persistence, prompts and HTTP."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from app import create_server
from backend.obol import ROOM_ID, CHARACTER_NAMES
from backend.rooms import get_room, is_mentioned, model_route
from backend.skills import SkillStore, parse_command
from backend.store import Store, default_settings
from backend.engine import _image_subjects, build_prompt
from backend.scenes import parse_scene_command, visible_conversation
from backend.visual_skills import character_visual_reference
from backend.remote_access import _route_allowed


class OfflineGateway:
    def status(self):
        return []


class ObolTests(unittest.TestCase):
    def test_six_speakers_keep_independent_model_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            c = store.create(room_id=ROOM_ID)
            self.assertEqual(c['settings']['participants'], list(CHARACTER_NAMES))
            models = {'magus': {'providerId': 'gpt', 'model': 'gpt-6.1-sol'}}
            store.update(c['id'], {'settings': {'models': models}})
            loaded = Store(directory).get(c['id'])
            self.assertEqual(loaded['settings']['models'], models)
            self.assertNotIn('orphie', loaded['settings']['models'])
        self.assertEqual(get_room(ROOM_ID)['name'], '404小队')
        self.assertEqual(get_room(ROOM_ID)['characters']['orphie']['name'], '奥菲丝')
        for slot in CHARACTER_NAMES:
            self.assertEqual(model_route(ROOM_ID, slot), ('gemini', 'gemini-4-argon'))

    def test_revisions_do_not_merge_partners_or_other_rooms(self):
        with tempfile.TemporaryDirectory() as directory:
            s = SkillStore(directory)
            s.update('magus', '语气稍微柔和一些', expected=0)
            loaded = SkillStore(directory)
            self.assertEqual(loaded.get('magus')['content'], '语气稍微柔和一些')
            self.assertEqual(loaded.get('orphie')['content'], '')
            self.assertEqual(loaded.get('gpt')['content'], '')
            self.assertEqual({item['id'] for item in loaded.list(ROOM_ID)}, set(CHARACTER_NAMES) | {'belle'})
            self.assertEqual(loaded.undo('magus', expected=1)['content'], '')
            self.assertEqual(parse_command('/设定 奥菲丝 今天带甜点', ROOM_ID)['id'], 'orphie')
            self.assertIsNone(parse_command('/设定 千夏 今天带甜点', ROOM_ID))

    def test_separate_names_and_visual_grounding(self):
        members = list(CHARACTER_NAMES)
        self.assertEqual(_image_subjects('404小队全员合影', ROOM_ID, members), (False, members))
        self.assertEqual(_image_subjects('给奥菲丝画头像', ROOM_ID, members)[1], ['orphie'])
        self.assertEqual(_image_subjects('只画鬼火', ROOM_ID, members)[1], ['magus'])
        self.assertEqual(_image_subjects('白银安比与11号合影', ROOM_ID, members)[1], ['soldier11', 'silver-anby'])
        self.assertTrue(is_mentioned(ROOM_ID, 'orphie', '@奥菲丝 你好'))
        self.assertFalse(is_mentioned(ROOM_ID, 'magus', '@奥菲丝 你好'))
        for slot, name in CHARACTER_NAMES.items():
            visual = character_visual_reference(slot, room_id=ROOM_ID)
            self.assertTrue(Path(visual['referencePath']).is_file())
            c = {'roomId': ROOM_ID, 'settings': default_settings(ROOM_ID), 'messages': []}
            prompt = build_prompt(slot, c, 1, False, 'OBOL_CUSTOM_SETTING')
            self.assertIn('你只扮演' + name, prompt)
            self.assertIn('OBOL_CUSTOM_SETTING', prompt)
        self.assertIn('机械龙头枪械', character_visual_reference('magus', room_id=ROOM_ID)['text'])
        self.assertIn('orphie-stand.png', character_visual_reference('magus', room_id=ROOM_ID)['referencePath'])

    def test_shared_body_does_not_leak_private_scene_history(self):
        scene, _ = parse_scene_command('/私聊 奥菲丝 | 想说一件小事', ROOM_ID)
        c = {'roomId': ROOM_ID, 'messages': [{'role': 'user', 'content': '私谈', 'audience': scene['audience']}]}
        self.assertEqual(len(visible_conversation(c, 'orphie')['messages']), 1)
        self.assertEqual(visible_conversation(c, 'magus')['messages'], [])

    def test_http_assets_and_skill_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(port=0, data_dir=directory, gateway=OfflineGateway())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def request(method, path, payload=None):
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=4)
                try:
                    conn.request(method, path, json.dumps(payload) if payload is not None else None,
                                 {'Content-Type': 'application/json'} if payload is not None else {})
                    response = conn.getresponse()
                    return response.status, response.read()
                finally:
                    conn.close()
            try:
                for slot in CHARACTER_NAMES:
                    for kind in ('stand', 'avatar'):
                        path = get_room(ROOM_ID)['characters'][slot][kind]
                        self.assertTrue(_route_allowed('GET', path))
                        status, body = request('GET', path)
                        self.assertEqual(status, 200, path)
                        self.assertTrue(body.startswith(b'\x89PNG'), path)
                status, body = request('GET', '/api/skills?roomId=zzz-obol')
                self.assertEqual(status, 200)
                self.assertIn('奥菲丝', body.decode())
                status, _ = request('POST', '/api/skills/magus', {'content': '说话更简短', 'expectedVersion': 0})
                self.assertEqual(status, 200)
                self.assertEqual(server.skills.get('orphie')['content'], '')
                self.assertEqual(request('GET', '/obol-theme.css')[0], 200)
                self.assertTrue(_route_allowed('GET', '/obol-theme.css'))
                self.assertFalse(_route_allowed('GET', '/assets/obol-unknown-stand.png'))
            finally:
                server.engine.stop_all()
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
