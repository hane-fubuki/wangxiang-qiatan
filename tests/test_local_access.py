"""Old bookmarks must reach one origin without exposing a second app."""
import http.client
import threading
import unittest
from unittest.mock import MagicMock, patch

import app
from backend.local_access import APP_PORT, canonical_port, create_local_redirect


class LocalRedirectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_local_redirect(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, method, path, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            c.request(method, path, headers=headers or {})
            r = c.getresponse()
            return r.status, dict(r.getheaders()), r.read()
        finally:
            c.close()

    def test_bookmark_keeps_path_and_query_at_fixed_canonical_origin(self):
        for method in ['GET', 'HEAD']:
            with self.subTest(method=method):
                status, headers, body = self.request(method, '/?v=lindverne-first-sword-20261017')
                self.assertEqual(status, 307)
                self.assertEqual(headers['Location'], 'http://127.0.0.1:8765/?v=lindverne-first-sword-20261017')
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertEqual(body, b'')

    def test_redirect_rejects_untrusted_host_and_absolute_targets(self):
        self.assertEqual(self.request('GET', '/', {'Host': 'outside.example'})[0], 403)
        for target in ['//outside.example/', 'https://outside.example/']:
            with self.subTest(target=target):
                status, headers, _ = self.request('GET', target, {'Host': f'127.0.0.1:{self.server.server_port}'})
                self.assertEqual(status, 400)
                self.assertNotIn('Location', headers)

    def test_old_page_cannot_replay_mutations_through_redirect(self):
        for method in ['POST', 'PATCH', 'DELETE', 'PUT']:
            with self.subTest(method=method):
                status, headers, _ = self.request(method, '/api/conversations')
                self.assertEqual(status, 409)
                self.assertNotIn('Location', headers)

    def test_legacy_cli_starts_one_app_and_closes_the_redirect(self):
        server = MagicMock(server_port=APP_PORT)
        server.serve_forever.side_effect = KeyboardInterrupt
        redirect = MagicMock()
        with patch('sys.argv', ['app.py', '--port', '8881']), \
                patch('app.create_server', return_value=server) as create, \
                patch('app.create_local_redirect', return_value=redirect), \
                patch('app.threading.Thread') as thread, patch('builtins.print'):
            app.main()
        create.assert_called_once_with(APP_PORT, None)
        thread.return_value.start.assert_called_once()
        redirect.shutdown.assert_called_once()
        redirect.server_close.assert_called_once()
        server.server_close.assert_called_once()

    def test_conflicting_old_port_releases_new_app_listener(self):
        server = MagicMock(server_port=APP_PORT)
        with patch('sys.argv', ['app.py']), \
                patch('app.create_server', return_value=server), \
                patch('app.create_local_redirect', side_effect=OSError('occupied')):
            with self.assertRaises(SystemExit):
                app.main()
        server.server_close.assert_called_once()
        server.serve_forever.assert_not_called()

    def test_other_test_ports_remain_independent(self):
        self.assertEqual(canonical_port(8772), 8772)
        self.assertEqual(canonical_port(8765), 8765)
        self.assertEqual(canonical_port(8881), 8765)


if __name__ == '__main__':
    unittest.main()
