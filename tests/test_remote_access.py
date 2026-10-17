"""Small proxy boundary tests; all traffic stays on temporary loopback ports."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
import time
import unittest

from backend.remote_access import COOKIE_NAME, MAX_BODY, MAX_RESPONSE, MAX_UPLOAD, _Auth, create_remote_server
from backend.releases import MAX_RELEASE_BYTES


# Transport-signature fixtures, not image-decoder fixtures. The real upstream
# separately verifies full image structure before storing an uploaded file.
IMAGE_BODIES = {"image/png": b"\x89PNG\r\n\x1a\n\x00binary-png",
                "image/jpeg": b"\xff\xd8\xff\xe0\x00binary-jpeg\xff\xd9",
                "image/webp": b"RIFF\x10\x00\x00\x00WEBP\x00binary-webp"}


class Upstream(BaseHTTPRequestHandler):
    requests = []
    mode = "normal"
    media_type = "image/png"

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.do_POST()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.requests.append((self.command, self.path, dict(self.headers), body))
        self.send_response(200)
        if self.path == "/downloads/latest.zip":
            self.send_header("Content-Type", "application/zip" if self.mode != "wrong-download-type" else "text/html")
            self.send_header("Content-Disposition", 'attachment; filename="wisdom-tavern-20261016-windows-x64.zip"'
                             if self.mode != "unsafe-download-name" else 'attachment; filename="../private.zip"')
            self.send_header("Content-Length", str(MAX_RELEASE_BYTES + 1) if self.mode == "huge-download" else "8")
            if self.mode == "duplicate-download-length":
                self.send_header("Content-Length", "8")
            self.end_headers()
            if self.mode != "huge-download":
                self.wfile.write(b"not-zip!" if self.mode == "invalid-download" else b"PK\x03\x04test")
            return
        media = self.path.startswith("/media/")
        self.send_header("Content-Type", self.media_type if media else "application/json")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Set-Cookie", "upstream-credential=must-not-be-forwarded")
        self.send_header("Location", "http://127.0.0.1/private")
        self.send_header("Content-Security-Policy", "default-src 'self'")
        if self.mode == "huge":
            self.send_header("Content-Length", str(MAX_RESPONSE + 1))
            self.end_headers()
            return
        payload = b"not-valid-json-private-error" if self.mode == "invalid" else IMAGE_BODIES.get(self.media_type, b"<html>unsafe</html>") if media else b'{"ok":true}'
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class RemoteAccessTests(unittest.TestCase):
    HOST = "tavern-tests.example"
    PASSWORD = "test-password-never-used-outside-tests"

    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        cls.upstream_thread = threading.Thread(target=cls.upstream.serve_forever, daemon=True)
        cls.upstream_thread.start()
        cls.proxy = create_remote_server(0, cls.upstream.server_port, cls.HOST, cls.PASSWORD)
        cls.proxy_thread = threading.Thread(target=cls.proxy.serve_forever, daemon=True)
        cls.proxy_thread.start()

    @classmethod
    def tearDownClass(cls):
        for server, thread in ((cls.proxy, cls.proxy_thread), (cls.upstream, cls.upstream_thread)):
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def setUp(self):
        Upstream.requests.clear()
        Upstream.mode = "normal"
        Upstream.media_type = "image/png"
        self.proxy.auth.sessions.clear()
        self.proxy.auth.failures.clear()

    def request(self, method, path, body=None, headers=None, cookie=None):
        request_headers = {"Host": self.HOST}
        if method != "GET":
            request_headers["Origin"] = "https://" + self.HOST
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        if cookie:
            request_headers["Cookie"] = cookie
        request_headers.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.proxy.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def cookie(self):
        status, token = self.proxy.auth.login(self.PASSWORD)
        self.assertEqual(status, 200)
        return COOKIE_NAME + "=" + token

    def test_forwarded_headers_are_rebuilt_and_upstream_cookies_never_escape(self):
        cookie = self.cookie()
        status, headers, _ = self.request("POST", "/api/conversations", b'{"roomId":"standard"}', cookie=cookie,
                                          headers={"Authorization": "Bearer private", "X-Forwarded-For": "10.0.0.5",
                                                   "X-Forwarded-Host": "attacker.example", "CF-Connecting-IP": "10.0.0.6",
                                                   "X-Forwarded-Proto": "https", "CF-Visitor": '{"scheme":"https"}'})
        self.assertEqual(status, 200)
        method, path, forwarded, body = Upstream.requests[-1]
        self.assertEqual((method, path, body), ("POST", "/api/conversations", b'{"roomId":"standard"}'))
        self.assertEqual(forwarded["Host"], f"127.0.0.1:{self.upstream.server_port}")
        self.assertEqual(forwarded["Origin"], f"http://127.0.0.1:{self.upstream.server_port}")
        self.assertEqual(set(forwarded), {"Host", "Origin", "Content-Type", "Content-Length", "Connection", "Accept-Encoding"})
        self.assertNotIn("Set-Cookie", headers)
        self.assertNotIn("Location", headers)
        self.assertEqual(headers["Content-Security-Policy"], "default-src 'self'")

    def test_grok_assets_require_login_and_are_available_through_proxy(self):
        for path in ("/assets/grok-original.jpg", "/assets/grok-avatar-reference.png"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 302)
                self.assertEqual(self.request("GET", path, cookie=self.cookie())[0], 200)
                self.assertEqual(Upstream.requests[-1][1], path)

    def test_tea_theme_assets_require_login_and_use_exact_paths(self):
        cookie = self.cookie()
        for path in ("/tea-theme.css", "/assets/tea-party-reference.jpg"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 302)
                self.assertEqual(self.request("GET", path, cookie=cookie)[0], 200)
                self.assertEqual(Upstream.requests[-1][1], path)
        before = len(Upstream.requests)
        for path in ("/tea-theme.css.bak", "/assets/tea-party-reference-original.jpg"):
            with self.subTest(private_path=path):
                self.assertEqual(self.request("GET", path, cookie=cookie)[0], 404)
        self.assertEqual(len(Upstream.requests), before)

    def test_login_inline_code_has_matching_nonce_and_no_unsafe_inline(self):
        status, headers, body = self.request("GET", "/login")
        self.assertIn("<title>登录 · 妄想洽谈中</title>", body.decode("utf-8"))
        self.assertIn("欢迎来到妄想洽谈中", body.decode("utf-8"))
        self.assertEqual(status, 200)
        nonces = re.findall(rb'nonce="([A-Za-z0-9_-]+)"', body)
        self.assertEqual(len(nonces), 2)
        self.assertEqual(nonces[0], nonces[1])
        self.assertIn("'nonce-" + nonces[0].decode() + "'", headers["Content-Security-Policy"])
        self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])
        self.assertFalse(Upstream.requests)

    def test_explicit_http_hint_redirects_get_and_rejects_password_post(self):
        for hints in ({"X-Forwarded-Proto": "http"}, {"CF-Visitor": '{"scheme":"http"}'},
                      {"X-Forwarded-Proto": "https", "CF-Visitor": '{"scheme":"http"}'}):
            with self.subTest(hints=hints):
                status, headers, body = self.request("GET", "/login", headers=hints)
                self.assertEqual(status, 308)
                self.assertEqual(headers["Location"], "https://" + self.HOST + "/login")
                self.assertNotIn(b'<input', body)
                status, _, _ = self.request("POST", "/api/auth/login", json.dumps({"password": self.PASSWORD}).encode(), headers=hints)
                self.assertEqual(status, 403)
        self.assertFalse(self.proxy.auth.sessions)
        self.assertFalse(Upstream.requests)

    def test_malformed_tunnel_hints_are_rejected_without_trusting_them(self):
        for hints in ({"X-Forwarded-Proto": "https,http"}, {"CF-Visitor": "not-json"},
                      {"CF-Visitor": '{"scheme":[]}'}, {"CF-Visitor": "[]"}):
            with self.subTest(hints=hints):
                self.assertEqual(self.request("GET", "/login", headers=hints)[0], 400)

    def test_large_requests_rejected_before_upstream_or_password_hash(self):
        status, _, _ = self.request("POST", "/api/conversations", b"", cookie=self.cookie(),
                                     headers={"Content-Length": str(MAX_BODY + 1)})
        self.assertEqual(status, 413)
        status, _, _ = self.request("POST", "/api/auth/login", b"", headers={"Content-Length": "4097"})
        self.assertEqual(status, 413)
        self.assertFalse(self.proxy.auth.failures)
        self.assertFalse(Upstream.requests)

    def test_invalid_or_excessive_upstream_response_is_safe(self):
        cookie = self.cookie()
        for mode in ("invalid", "huge"):
            Upstream.mode = mode
            with self.subTest(mode=mode):
                status, _, body = self.request("GET", "/api/bootstrap", cookie=cookie)
                self.assertEqual(status, 502)
                self.assertNotIn(b"private", body)
                self.assertNotIn(b"127.0.0.1", body)

    def test_download_size_type_framing_and_filename_are_validated(self):
        cookie = self.cookie()
        for mode in ("huge-download", "wrong-download-type", "unsafe-download-name",
                     "duplicate-download-length", "invalid-download"):
            Upstream.mode = mode
            with self.subTest(mode=mode):
                status, headers, body = self.request("GET", "/downloads/latest.zip", cookie=cookie)
                self.assertEqual(status, 502)
                self.assertNotIn("Content-Disposition", headers)
                self.assertNotIn(b"private", body)

    def test_download_login_returns_only_to_the_fixed_download_path(self):
        status, headers, _ = self.request("GET", "/downloads/latest.zip")
        self.assertEqual((status, headers["Location"]), (302, "/login?download=1"))
        status, _, body = self.request("GET", headers["Location"])
        self.assertEqual(status, 200)
        self.assertIn(b'location.replace("/downloads/latest.zip")', body)
        for path in ("/login", "/login?next=https://attacker.example"):
            body = self.request("GET", path)[2]
            self.assertIn(b'location.replace("/")', body)
            self.assertNotIn(b"attacker.example", body)

    def test_original_double_slash_and_absolute_urls_are_rejected_after_login(self):
        cookie = self.cookie()
        for path in ("//api/bootstrap", "///api/bootstrap", "http://attacker.example/api/bootstrap",
                     "/api/../api/bootstrap", "/api/%62ootstrap", "/api/bootstrap#fragment"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path, cookie=cookie)[0], 400)
        self.assertFalse(Upstream.requests)

    def test_unsupported_methods_never_reach_upstream(self):
        cookie = self.cookie()
        for method in ("PUT", "TRACE", "OPTIONS", "CONNECT"):
            with self.subTest(method=method):
                self.assertEqual(self.request(method, "/api/bootstrap", cookie=cookie)[0], 405)
        self.assertFalse(Upstream.requests)

    def test_malformed_unicode_password_is_a_failed_login_not_a_disconnected_request(self):
        status, _, _ = self.request("POST", "/api/auth/login", b'{"password":"\\ud800"}')
        self.assertEqual(status, 401)
        self.assertEqual(self.proxy.auth._checking, 0)

    def test_host_activation_validates_before_changing_state_and_is_one_time(self):
        proxy = create_remote_server(0, self.upstream.server_port, password=self.PASSWORD)
        try:
            self.assertEqual(proxy.server_address[0], "127.0.0.1")
            for host in ("https://example.com", "example.com:443", "example.com/", "EXAMPLE.COM", "localhost"):
                with self.subTest(host=host), self.assertRaises(ValueError):
                    proxy.set_public_host(host)
                self.assertIsNone(proxy.public_host)
            proxy.set_public_host(self.HOST)
            with self.assertRaises(ValueError):
                proxy.set_public_host("other.example")
            self.assertEqual(proxy.public_host, self.HOST)
        finally:
            proxy.server_close()

    def test_session_limit_evicts_oldest_and_stores_only_token_hash(self):
        auth = _Auth(self.PASSWORD)
        now = time.monotonic()
        auth.sessions.update({str(index): now + index + 1 for index in range(256)})
        status, token = auth.login(self.PASSWORD)
        self.assertEqual(status, 200)
        self.assertEqual(len(auth.sessions), 256)
        self.assertNotIn("0", auth.sessions)
        self.assertNotIn(token, auth.sessions)
        self.assertFalse(auth.failures)

    def test_skill_routes_forward_json_only_after_authentication(self):
        routes = [("GET", "/api/skills", None)]
        routes.extend(("POST", "/api/skills/" + provider + suffix, b'{"instruction":"test"}')
                      for provider in ("deepseek", "gemini", "gpt") for suffix in ("", "/undo"))
        cookie = self.cookie()
        for method, path, body in routes:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.request(method, path, body)[0], 401)
                self.assertEqual(self.request(method, path, body, cookie=cookie)[0], 200)
                self.assertEqual(Upstream.requests[-1][:2], (method, path))
                self.assertEqual(Upstream.requests[-1][3], body or b"")
        self.assertEqual(len(Upstream.requests), len(routes))

    def test_only_exact_skill_and_media_routes_are_allowed(self):
        cookie = self.cookie()
        media_id = "1a" * 16
        for method, path in (("POST", "/api/skills/unknown"), ("POST", "/api/skills/gpt/reset"),
                             ("POST", "/api/skills/gpt/undo/"), ("GET", "/api/skills/gpt"),
                             ("POST", "/media/" + media_id), ("GET", "/media/" + media_id.upper()),
                             ("GET", "/media/" + media_id + ".png"), ("GET", "/media/" + "a" * 31),
                             ("GET", "/media/../.env"), ("GET", "/media/%31" + media_id[1:])):
            with self.subTest(method=method, path=path):
                self.assertIn(self.request(method, path, b"{}" if method == "POST" else None, cookie=cookie)[0], (400, 404))
        self.assertFalse(Upstream.requests)

    def test_authenticated_raw_image_upload_preserves_supported_mime_and_bytes(self):
        cookie = self.cookie()
        for mime, body in IMAGE_BODIES.items():
            with self.subTest(mime=mime):
                status, _, _ = self.request("POST", "/api/media", body, cookie=cookie,
                                             headers={"Content-Type": mime, "Authorization": "private-client-token"})
                self.assertEqual(status, 200)
                method, path, forwarded, received = Upstream.requests[-1]
                self.assertEqual((method, path, received), ("POST", "/api/media", body))
                self.assertEqual(forwarded["Content-Type"], mime)
                self.assertEqual(forwarded["Content-Length"], str(len(body)))
                self.assertEqual(forwarded["Origin"], f"http://127.0.0.1:{self.upstream.server_port}")
                self.assertNotIn("Cookie", forwarded)
                self.assertNotIn("Authorization", forwarded)

    def test_image_upload_and_media_reads_require_login_and_same_origin(self):
        body = IMAGE_BODIES["image/png"]
        headers = {"Content-Type": "image/png"}
        self.assertEqual(self.request("POST", "/api/media", body, headers=headers)[0], 401)
        status, response_headers, payload = self.request("GET", "/media/" + "a" * 32)
        self.assertEqual(status, 302)
        self.assertEqual(response_headers["Location"], "/login")
        self.assertEqual(payload, b"")
        cookie = self.cookie()
        for extra in ({"Host": "attacker.example"}, {"Origin": "https://attacker.example"},
                      {"Origin": "null"}, {"Transfer-Encoding": "chunked"}):
            with self.subTest(extra=extra):
                status, _, _ = self.request("POST", "/api/media", body, cookie=cookie, headers={**headers, **extra})
                self.assertIn(status, (400, 403))
        self.assertFalse(Upstream.requests)

    def test_image_type_and_signature_mismatch_are_rejected_before_forwarding(self):
        cookie = self.cookie()
        for mime, body, extra in (("text/html", b"<html>unsafe</html>", {}),
                                  ("application/json", b"{}", {}), ("image/svg+xml", b"<svg/>", {}),
                                  ("image/png", b"<html>unsafe</html>", {}),
                                  ("image/jpeg", IMAGE_BODIES["image/png"], {}),
                                  ("image/png", IMAGE_BODIES["image/png"], {"Content-Encoding": "gzip"})):
            with self.subTest(mime=mime, extra=extra):
                self.assertEqual(self.request("POST", "/api/media", body, cookie=cookie,
                                               headers={"Content-Type": mime, **extra})[0], 415)
        self.assertEqual(self.request("POST", "/api/media", b"", cookie=cookie,
                                       headers={"Content-Type": "image/png"})[0], 400)
        self.assertFalse(Upstream.requests)

    def test_eight_mib_upload_limit_does_not_expand_other_api_limits(self):
        cookie = self.cookie()
        prefix = IMAGE_BODIES["image/png"]
        full = prefix + b"\x00" * (MAX_UPLOAD - len(prefix))
        self.assertEqual(self.request("POST", "/api/media", full, cookie=cookie,
                                       headers={"Content-Type": "image/png"})[0], 200)
        self.assertEqual(len(Upstream.requests[-1][3]), MAX_UPLOAD)
        Upstream.requests.clear()
        for path, length, mime in (("/api/media", MAX_UPLOAD + 1, "image/png"),
                                   ("/api/conversations", MAX_BODY + 1, "application/json"),
                                   ("/api/skills/gpt", MAX_BODY + 1, "application/json"),
                                   ("/api/skills/gpt/undo", MAX_BODY + 1, "application/json"),
                                   ("/api/auth/login", 4097, "application/json")):
            with self.subTest(path=path):
                self.assertEqual(self.request("POST", path, b"", cookie=cookie,
                                               headers={"Content-Type": mime, "Content-Length": str(length)})[0], 413)
        self.assertFalse(Upstream.requests)

    def test_media_response_keeps_safe_mime_and_is_never_publicly_cacheable(self):
        cookie = self.cookie()
        for mime, body in IMAGE_BODIES.items():
            Upstream.media_type = mime
            with self.subTest(mime=mime):
                status, headers, payload = self.request("GET", "/media/" + "a" * 32, cookie=cookie)
                self.assertEqual(status, 200)
                self.assertEqual(payload, body)
                self.assertEqual(headers["Content-Type"], mime)
                self.assertEqual(headers["Cache-Control"], "private, no-store")
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertNotIn("Set-Cookie", headers)
        Upstream.media_type = "text/html"
        self.assertEqual(self.request("GET", "/media/" + "a" * 32, cookie=cookie)[0], 502)
        Upstream.media_type = "image/png"
        Upstream.mode = "invalid"
        self.assertEqual(self.request("GET", "/media/" + "a" * 32, cookie=cookie)[0], 502)


if __name__ == "__main__":
    unittest.main()
