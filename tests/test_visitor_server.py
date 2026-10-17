"""Private room, media, local connection and proxy boundaries with synthetic data."""
from http.cookies import SimpleCookie
import http.client
import json
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import patch

from app import create_server
from backend.engine import Run
from backend.remote_access import create_remote_server
from backend.store import make_message
from tests.test_media_server import FakeMedia, UPLOADED_PNG


class Gateway:
    def status(self):
        return [{"id": p, "name": p, "model": "test-model", "configured": True}
                for p in ('deepseek', 'gemini', 'gpt', 'grok')]

    def room_status(self, room, assignments=None):
        ids = ('gemini', 'deepseek', 'gpt', 'paimon', 'xiangling', 'xiao', 'zibai') if room == 'wangsheng-trio' else ('deepseek', 'gemini', 'gpt', 'grok')
        return [{"id": p, "name": p, "model": "test-model", "configured": True} for p in ids]

    def respond(self, provider, prompt, cancel):
        return json.dumps({"speak": False, "to": "everyone", "content": ""})


class Browser:
    def __init__(self, server, host=None):
        self.server = server
        self.host = host or f'127.0.0.1:{server.server_port}'
        self.origin = ('https://' if host else 'http://') + self.host
        self.cookies = {}

    def request(self, method, path, data=None, *, raw=None, headers=None):
        body = raw if raw is not None else json.dumps(data).encode() if data is not None else None
        supplied = {'Host': self.host}
        if method != 'GET':
            supplied['Origin'] = self.origin
        if body is not None:
            supplied['Content-Type'] = 'application/json'
        if self.cookies:
            supplied['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
        supplied.update(headers or {})
        supplied = {k: v for k, v in supplied.items() if v is not None}
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body, supplied)
            response = connection.getresponse()
            payload = response.read()
            response_headers = dict(response.getheaders())
            for value in response.headers.get_all('Set-Cookie', []):
                jar = SimpleCookie(value)
                self.cookies.update({k: m.value for k, m in jar.items()})
            if response.getheader('Content-Type', '').startswith('application/json'):
                payload = json.loads(payload)
            return response.status, payload, response_headers
        finally:
            connection.close()


class VisitorServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media = FakeMedia(self.temp.name)
        self.server = create_server(0, self.temp.name, gateway=Gateway(), codex_media=self.media)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.a, self.b = Browser(self.server), Browser(self.server)
        self.a.request('GET', '/api/bootstrap')
        self.b.request('GET', '/api/bootstrap')

    def stop(self):
        self.media.release.set()
        self.server.engine.stop_all()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)

    def create(self, browser, room='wangsheng-trio'):
        status, result, _ = browser.request('POST', '/api/conversations', {'roomId': room})
        self.assertEqual(status, 201, result)
        self.assertNotIn('ownerId', result)
        return result['id']

    def test_private_crud_runs_and_legacy_shared_chats(self):
        private = self.create(self.a)
        shared = self.create(self.a, 'zzz-trio')
        old = self.server.store.create('wangsheng-trio')['id']
        self.assertEqual(self.server.store.get(private)['ownerId'], self.a.cookies['tavern_visitor'])
        for method, route, payload in [('GET', '', None), ('PATCH', '', {'title': 'wrong'}),
                                       ('DELETE', '', None), ('POST', '/messages', {'content': 'wrong'}),
                                       ('POST', '/continue', {})]:
            self.assertEqual(self.b.request(method, '/api/conversations/' + private + route, payload)[0], 404)
        self.assertEqual(self.b.request('GET', '/api/conversations/' + shared)[0], 200)
        self.assertEqual(self.b.request('GET', '/api/conversations/' + old)[0], 200)
        run = Run('a' * 32, private)
        self.server.engine.active[private] = run
        status, other, _ = self.b.request('GET', '/api/bootstrap')
        self.assertEqual(status, 200)
        self.assertNotIn(private, [item['id'] for item in other['conversations']])
        self.assertNotIn(private, other['activeRuns'])
        self.assertNotIn(private, other['runStates'])
        mine = self.a.request('GET', '/api/bootstrap')[1]
        self.assertIn(private, mine['activeRuns'])
        self.assertNotIn('ownerId', json.dumps(mine))
        self.assertEqual(self.b.request('POST', '/api/runs/' + run.id + '/stop', {})[0], 404)
        self.assertFalse(run.cancel.is_set())
        self.assertEqual(self.a.request('POST', '/api/runs/' + run.id + '/stop', {})[0], 200)
        self.assertTrue(run.cancel.is_set())
        self.assertEqual(self.a.request('PATCH', '/api/conversations/' + private, {'title': 'my table'})[0], 200)
        self.assertEqual(self.a.request('DELETE', '/api/conversations/' + private)[0], 200)

    def test_sse_events_are_filtered_even_after_deletion(self):
        cid = self.create(self.a)
        a, b = queue.Queue(), queue.Queue()
        self.server.events.listeners[a] = self.a.cookies['tavern_visitor']
        self.server.events.listeners[b] = self.b.cookies['tavern_visitor']
        conversation = self.server.store.get(cid)
        self.server.events.emit('conversation', {'conversation': conversation})
        payload = a.get_nowait()
        self.assertNotIn(b'ownerId', payload)
        self.assertNotIn(conversation['ownerId'].encode(), payload)
        self.assertTrue(b.empty())
        self.a.request('DELETE', '/api/conversations/' + cid)
        self.assertIn(b'event: deleted', a.get_nowait())
        self.assertTrue(b.empty())
        self.server.events.emit('message', {'conversationId': cid, 'message': {'content': 'late private event'}})
        self.assertIn(b'late private event', a.get_nowait())
        self.assertTrue(b.empty())
        self.server.events.emit('skills', {'id': 'gpt', 'version': 1})
        self.assertIn(b'event: skills', b.get_nowait())

    def test_upload_claim_and_legacy_media_publication(self):
        status, image, _ = self.a.request('POST', '/api/media', raw=UPLOADED_PNG, headers={'Content-Type': 'image/png'})
        self.assertEqual(status, 201)
        self.assertEqual(self.a.request('GET', image['url'])[0], 200)
        self.assertEqual(self.b.request('GET', image['url'])[0], 404)
        other_private = self.create(self.b)
        self.assertEqual(self.b.request('POST', f'/api/conversations/{other_private}/messages',
                                       {'content': '描述图片', 'attachments': [image['id']]})[0], 404)
        shared = self.create(self.a, 'standard')
        self.assertEqual(self.b.request('POST', f'/api/conversations/{shared}/messages',
                                       {'content': '描述图片', 'attachments': [image['id']]})[0], 404)
        with patch.object(self.server.engine, 'start', return_value={'conversation': self.server.store.get(shared)}):
            self.assertEqual(self.a.request('POST', f'/api/conversations/{shared}/messages',
                                           {'content': '描述图片', 'attachments': [image['id']]})[0], 200)
        self.assertEqual(self.b.request('GET', image['url'])[0], 200)
        legacy = self.server.media.add(UPLOADED_PNG)
        self.assertEqual(self.b.request('GET', legacy['url'])[0], 200)

    def test_local_connection_origin_boundary_and_metadata(self):
        status, value, _ = self.a.request('GET', '/api/local-connection')
        self.assertEqual(status, 200)
        self.assertFalse(value['hasKey'])
        secret = 'synthetic-api-key-not-used-on-network'
        config = {'baseUrl': 'https://models.example/v1', 'apiKey': secret, 'model': 'test-model'}
        self.assertEqual(self.a.request('POST', '/api/local-connection/save', config, headers={'Origin': None})[0], 403)
        self.assertEqual(self.a.request('POST', '/api/local-connection/save', config, headers={'Origin': 'https://other.example'})[0], 403)
        status, saved, _ = self.a.request('POST', '/api/local-connection/save', config)
        self.assertEqual(status, 200, saved)
        self.assertTrue(saved['hasKey'])
        self.assertNotIn(secret, json.dumps(saved))
        self.assertNotIn(secret.encode(), self.server.local_connection.path.read_bytes())
        self.assertNotIn(secret, json.dumps(self.a.request('GET', '/api/local-connection')[1]))
        with patch.object(self.server.local_connection, 'test', return_value={'ok': True, 'message': 'fake OK'}) as test:
            self.assertEqual(self.a.request('POST', '/api/local-connection/test', config)[0], 200)
            test.assert_called_once()
        self.assertEqual(self.a.request('POST', '/api/local-connection/clear', {})[0], 200)
        self.assertFalse(self.server.local_connection.path.exists())

    def test_new_assets_use_explicit_allowlist(self):
        for name in ('wangsheng-room.png', 'wangsheng-gemini-stand.png', 'wangsheng-gpt-avatar.png', 'wangsheng-zibai.png', 'wangsheng-xiao.svg'):
            self.assertEqual(self.a.request('GET', '/assets/' + name)[0], 200, name)
        for name in ('wangsheng-private.json', 'wangsheng-room.svg', 'wangsheng-unknown.png'):
            self.assertEqual(self.a.request('GET', '/assets/' + name)[0], 404, name)

    def test_proxy_filters_cookie_and_keeps_local_settings_private(self):
        proxy = create_remote_server(0, self.server.server_port, 'visitor-tests.example', 'synthetic-proxy-password')
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        try:
            a, b = Browser(proxy, 'visitor-tests.example'), Browser(proxy, 'visitor-tests.example')
            for browser in (a, b):
                self.assertEqual(browser.request('POST', '/api/auth/login', {'password': 'synthetic-proxy-password'})[0], 200)
                status, boot, headers = browser.request('GET', '/api/bootstrap')
                self.assertEqual(status, 200)
                self.assertFalse(boot['capabilities']['localConnection']['available'])
                cookie = SimpleCookie(headers['Set-Cookie'])['tavern_visitor']
                self.assertTrue(cookie['secure'])
                self.assertTrue(cookie['httponly'])
            private = self.create(a)
            self.assertEqual(b.request('GET', '/api/conversations/' + private)[0], 404)
            self.assertEqual(a.request('GET', '/api/conversations/' + private)[0], 200)
            self.assertNotIn(private, [c['id'] for c in b.request('GET', '/api/bootstrap')[1]['conversations']])
            for method, route in [('GET', ''), ('POST', '/save'), ('POST', '/test'), ('POST', '/clear')]:
                self.assertEqual(a.request(method, '/api/local-connection' + route, {} if method == 'POST' else None)[0], 404)
            self.assertFalse(a.request('POST', '/api/providers/refresh', {})[1]['capabilities']['localConnection']['available'])
            captured = []
            original = self.server.RequestHandlerClass._visitor
            def inspect(handler):
                captured.append(dict(handler.headers))
                original(handler)
            a.cookies['other-cookie'] = 'do-not-forward'
            with patch.object(self.server.RequestHandlerClass, '_visitor', inspect):
                a.request('GET', '/api/bootstrap', headers={'Authorization': 'do-not-forward'})
            self.assertEqual(captured[-1].get('Cookie'), 'tavern_visitor=' + a.cookies['tavern_visitor'])
            self.assertNotIn('Authorization', captured[-1])
            status, image, _ = a.request('POST', '/api/media', raw=UPLOADED_PNG, headers={'Content-Type': 'image/png'})
            self.assertEqual(status, 201)
            self.assertEqual(a.request('GET', image['url'])[0], 200)
            self.assertEqual(b.request('GET', image['url'])[0], 404)
        finally:
            proxy.shutdown()
            proxy.server_close()
            thread.join(3)


if __name__ == '__main__':
    unittest.main()
