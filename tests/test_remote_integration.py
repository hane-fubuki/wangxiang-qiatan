"""Independent remote-gate checks against a real, disposable loopback app.

No public tunnel, real provider, or user conversation storage is used.
"""
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from app import create_server
from backend.remote_access import create_remote_server
from backend.rooms import public_rooms
from backend.store import make_message


class FakeGateway:
    credential = "private-upstream-credential-must-never-be-serialized"

    def status(self):
        return [{"id": provider, "name": provider, "configured": True, "model": "fake-model"}
                for provider in ("deepseek", "gemini", "gpt")]

    def respond(self, provider, prompt, cancel):
        return json.dumps({"speak": True, "to": "user", "content": provider + " 独立测试回复"})


class RemoteIntegrationTests(unittest.TestCase):
    HOST = "private-tavern.example"
    ORIGIN = "https://" + HOST
    PASSWORD = "independent-integration-password-only-not-a-real-secret"
    PRIVATE_MARKER = "仅存在于临时测试历史的私有标记"

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.backend = create_server(port=0, data_dir=Path(cls.temp.name) / "upstream", gateway=FakeGateway())
        # Test proxy behavior independently of deliberate presentation delays.
        engine = cls.backend.engine
        reply_clock = patch.object(engine, "_wait_for_reply", side_effect=lambda run, provider: engine._current(run))
        reply_clock.start()
        cls.addClassCleanup(reply_clock.stop)
        conversation = cls.backend.store.create("zzz-trio")
        cls.cid = conversation["id"]
        cls.backend.store.append(cls.cid, make_message("user", cls.PRIVATE_MARKER))
        cls.backend_thread = threading.Thread(target=cls.backend.serve_forever, daemon=True)
        cls.backend_thread.start()
        cls.remote = create_remote_server(port=0, upstream_port=cls.backend.server_port,
                                          public_host=cls.HOST, password=cls.PASSWORD)
        cls.remote_thread = threading.Thread(target=cls.remote.serve_forever, daemon=True)
        cls.remote_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.remote.shutdown()
        cls.remote.server_close()
        cls.remote_thread.join(timeout=3)
        cls.backend.engine.stop_all()
        cls.backend.starters.cancel_all()
        cls.backend.shutdown()
        cls.backend.server_close()
        cls.backend_thread.join(timeout=3)
        cls.temp.cleanup()

    def setUp(self):
        self.remote.auth.failures.clear()
        self.remote.auth.sessions.clear()

    def request(self, method, path, payload=None, headers=None, cookie=None, server=None):
        supplied = {"Host": self.HOST}
        if method in ("POST", "PATCH", "DELETE"):
            supplied["Origin"] = self.ORIGIN
        body = None if payload is None else json.dumps(payload).encode()
        if body is not None:
            supplied["Content-Type"] = "application/json"
        if cookie:
            supplied["Cookie"] = cookie
        supplied.update(headers or {})
        supplied = {name: value for name, value in supplied.items() if value is not None}
        connection = http.client.HTTPConnection("127.0.0.1", (server or self.remote).server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=supplied)
            response = connection.getresponse()
            response_body = response.read()
            result_headers = dict(response.getheaders())
            if response_body and response.getheader("Content-Type", "").startswith("application/json"):
                response_body = json.loads(response_body)
            return response.status, response_body, result_headers
        finally:
            connection.close()

    def login(self):
        status, payload, headers = self.request("POST", "/api/auth/login", {"password": self.PASSWORD})
        self.assertEqual(status, 200, payload)
        cookies = SimpleCookie()
        cookies.load(headers["Set-Cookie"])
        morsel = cookies["__Host-tavern_session"]
        self.assertTrue(morsel["secure"])
        self.assertTrue(morsel["httponly"])
        self.assertEqual(morsel["samesite"].lower(), "strict")
        self.assertEqual(morsel["path"], "/")
        self.assertEqual(morsel["domain"], "")
        self.assertNotEqual(morsel.value, self.PASSWORD)
        return "__Host-tavern_session=" + morsel.value

    def assert_no_private_data(self, body):
        text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False)
        for secret in (self.PRIVATE_MARKER, self.PASSWORD, FakeGateway.credential):
            self.assertNotIn(secret, text)

    def test_anonymous_requests_cannot_read_or_modify_history_or_assets(self):
        before = self.backend.store.list()
        for path in ("/api/bootstrap", f"/api/conversations/{self.cid}", "/api/events"):
            with self.subTest(path=path):
                status, body, _ = self.request("GET", path)
                self.assertEqual(status, 401)
                self.assert_no_private_data(body)
        for path in ("/", "/index.html", "/app.js", "/styles.css", "/assets/user-avatar.png",
                     "/assets/zzz-sunna-stand.png"):
            with self.subTest(path=path):
                status, body, headers = self.request("GET", path)
                self.assertIn(status, (302, 303, 401))
                if status in (302, 303):
                    self.assertEqual(headers["Location"], "/login")
                self.assert_no_private_data(body)
        for method, path, payload in (("POST", "/api/conversations", {}),
                                      ("PATCH", f"/api/conversations/{self.cid}", {"title": "unauthorized"}),
                                      ("DELETE", f"/api/conversations/{self.cid}", None),
                                      ("POST", f"/api/conversations/{self.cid}/messages", {"content": "unauthorized"}),
                                      ("POST", "/api/starters/generate", {"starterId": "ideas"}),
                                      ("POST", "/api/providers/refresh", {}),
                                      ("POST", "/api/runs/" + "0" * 32 + "/stop", {})):
            with self.subTest(method=method, path=path):
                status, body, _ = self.request(method, path, payload)
                self.assertEqual(status, 401)
                self.assert_no_private_data(body)
        self.assertEqual(self.backend.store.list(), before)

    def test_anonymous_health_is_minimal_and_login_page_has_no_secrets(self):
        status, body, headers = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        status, body, headers = self.request("GET", "/login")
        self.assertEqual(status, 200)
        self.assert_no_private_data(body)
        self.assertNotIn(b"/api/conversations", body)
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_bound_proxy_denies_everything_until_public_host_activation(self):
        gate = create_remote_server(port=0, upstream_port=self.backend.server_port,
                                    public_host=None, password=self.PASSWORD)
        runner = threading.Thread(target=gate.serve_forever, daemon=True)
        runner.start()
        try:
            for method, path, payload in (("GET", "/api/health", None), ("GET", "/login", None),
                                          ("GET", "/api/bootstrap", None),
                                          ("POST", "/api/auth/login", {"password": self.PASSWORD})):
                with self.subTest(method=method, path=path):
                    status, body, _ = self.request(method, path, payload, server=gate)
                    self.assertIn(status, (403, 503))
                    self.assert_no_private_data(body)
            gate.set_public_host(self.HOST)
            self.assertEqual(self.request("GET", "/api/health", server=gate)[0], 200)
            self.assertEqual(self.request("GET", "/api/bootstrap", server=gate)[0], 401)
        finally:
            gate.shutdown()
            gate.server_close()
            runner.join(timeout=3)

    def test_cookie_session_grants_access_and_logout_revokes_it(self):
        cookie = self.login()
        status, payload, headers = self.request("GET", "/api/bootstrap", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        self.assertEqual(payload["eventTransport"], "poll")
        self.assertEqual({room["id"] for room in payload["rooms"]}, {room["id"] for room in public_rooms()})
        self.assertIn("userProfile", payload)
        self.assertIn("activeRuns", payload)
        self.assertTrue(any(item["id"] == self.cid and item["messages"][0]["content"] == self.PRIVATE_MARKER
                            for item in payload["conversations"]))
        self.assertNotIn(self.PASSWORD, json.dumps(payload))
        self.assertNotIn(FakeGateway.credential, json.dumps(payload))
        status, _, headers = self.request("POST", "/api/auth/logout", {}, cookie=cookie)
        self.assertIn(status, (200, 204))
        self.assertIn("Max-Age=0", headers.get("Set-Cookie", ""))
        self.assertEqual(self.request("GET", "/api/bootstrap", cookie=cookie)[0], 401)

    def test_session_expiry_and_forged_cookie_are_rejected(self):
        cookie = self.login()
        token = cookie.split("=", 1)[1]
        digest = hashlib.sha256(token.encode()).hexdigest()
        self.remote.auth.sessions[digest] = time.monotonic() - 1
        self.assertEqual(self.request("GET", "/api/bootstrap", cookie=cookie)[0], 401)
        self.assertEqual(self.request("GET", "/api/bootstrap", cookie="__Host-tavern_session=forged")[0], 401)
        self.assertEqual(self.request("GET", "/api/bootstrap", cookie="bad@key=1; __Host-tavern_session=abc")[0], 401)
        self.assertEqual(self.request("GET", "/api/bootstrap", headers={"Authorization": "Bearer " + self.PASSWORD})[0], 401)
        self.assertEqual(self.request("GET", "/api/bootstrap?password=" + self.PASSWORD)[0], 401)

    def test_untrusted_host_origin_and_forwarded_headers_do_not_bypass_the_gate(self):
        cookie = self.login()
        before = self.backend.store.list()
        for headers in ({"Host": "attacker.example"}, {"Host": self.HOST + ".attacker.example"},
                        {"Host": "127.0.0.1:" + str(self.remote.server_port)},
                        {"Origin": "https://attacker.example"}, {"Origin": "http://" + self.HOST},
                        {"Origin": "null"}, {"Origin": None}):
            with self.subTest(headers=headers):
                status, body, _ = self.request("POST", "/api/conversations", {}, headers=headers, cookie=cookie)
                self.assertEqual(status, 403)
                self.assert_no_private_data(body)
        status, body, _ = self.request("GET", "/api/bootstrap", headers={"X-Forwarded-Host": self.HOST,
                                                                          "X-Forwarded-Proto": "https",
                                                                          "CF-Connecting-IP": "1.2.3.4"})
        self.assertEqual(status, 401)
        self.assert_no_private_data(body)
        self.assertEqual(self.backend.store.list(), before)

    def test_failed_login_is_rate_limited_even_when_client_ip_headers_change(self):
        codes = []
        for attempt in range(10):
            status, body, _ = self.request("POST", "/api/auth/login", {"password": "wrong"},
                                           headers={"CF-Connecting-IP": f"10.0.0.{attempt}", "X-Forwarded-For": f"10.0.1.{attempt}"})
            codes.append(status)
            self.assert_no_private_data(body)
        self.assertEqual(codes[0], 401)
        self.assertIn(429, codes)
        self.assertEqual(codes[-1], 429)

    def test_ambiguous_headers_and_transfer_encoding_never_reach_the_app(self):
        cookie = self.login()
        before = self.backend.store.list()
        base_headers = [("Host", self.HOST), ("Origin", self.ORIGIN),
                        ("Cookie", cookie), ("Content-Type", "application/json"),
                        ("Content-Length", "2")]
        for extra in (("Host", "attacker.example"), ("Origin", "https://attacker.example"),
                      ("Content-Length", "2"), ("Content-Type", "text/plain"),
                      ("Transfer-Encoding", "chunked"), ("Cookie", cookie)):
            with self.subTest(extra=extra[0]):
                connection = http.client.HTTPConnection("127.0.0.1", self.remote.server_port, timeout=5)
                try:
                    connection.putrequest("POST", "/api/conversations", skip_host=True,
                                          skip_accept_encoding=True)
                    for name, value in [*base_headers, extra]:
                        connection.putheader(name, value)
                    connection.endheaders(b"{}")
                    response = connection.getresponse()
                    self.assertIn(response.status, (400, 401, 403))
                    self.assert_no_private_data(response.read())
                finally:
                    connection.close()
        self.assertEqual(self.backend.store.list(), before)

    def test_encoded_absolute_and_private_paths_never_serve_sensitive_files(self):
        paths = ("/.env", "/backend/remote_access.py", "/.tavern/conversations.json", "/assets/PROMPTS.md",
                 "/assets/USER-AVATAR-PROMPT.md", "/../app.py", "/%2e%2e/app.py", "/%252e%252e/app.py",
                 "/login/../api/bootstrap", "//api/bootstrap", "/%61pi/bootstrap", "/login%2f..%2fapi/bootstrap",
                 "http://attacker.example/api/bootstrap", "/api/bootstrap%00")
        for path in paths:
            with self.subTest(anonymous_path=path):
                status, body, _ = self.request("GET", path)
                self.assertNotEqual(status, 200)
                self.assert_no_private_data(body)
        cookie = self.login()
        for path in paths[:8]:
            with self.subTest(authenticated_path=path):
                status, body, _ = self.request("GET", path, cookie=cookie)
                self.assertIn(status, (400, 403, 404))
                self.assert_no_private_data(body)

    def test_authenticated_proxy_preserves_crud_and_chat_poll_results(self):
        cookie = self.login()
        status, conversation, _ = self.request("POST", "/api/conversations", {"roomId": "zzz-trio"}, cookie=cookie)
        self.assertEqual(status, 201)
        cid = conversation["id"]
        self.assertEqual(conversation["roomId"], "zzz-trio")
        status, result, _ = self.request("POST", f"/api/conversations/{cid}/messages",
                                          {"content": "这是临时远程代理测试", "settings": {"maxRounds": 1}}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("runId", result)
        for _ in range(100):
            if cid not in self.backend.engine.snapshot():
                break
            threading.Event().wait(0.01)
        status, payload, _ = self.request("GET", "/api/bootstrap", cookie=cookie)
        self.assertEqual(status, 200)
        conversation = next(item for item in payload["conversations"] if item["id"] == cid)
        self.assertEqual({m["provider"] for m in conversation["messages"] if m["role"] == "assistant"}, {"deepseek", "gemini", "gpt"})
        self.assertNotIn(cid, payload["activeRuns"])
        status, _, _ = self.request("PATCH", f"/api/conversations/{cid}", {"title": "远程标题"}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(self.request("GET", f"/api/conversations/{cid}", cookie=cookie)[1]["title"], "远程标题")
        self.assertEqual(self.request("DELETE", f"/api/conversations/{cid}", cookie=cookie)[0], 200)
        self.assertEqual(self.request("GET", f"/api/conversations/{cid}", cookie=cookie)[0], 404)

    def test_remote_events_do_not_open_an_sse_connection_and_assets_stay_authenticated(self):
        cookie = self.login()
        started = time.monotonic()
        status, _, headers = self.request("GET", "/api/events", cookie=cookie)
        self.assertNotEqual(status, 200)
        self.assertNotIn("text/event-stream", headers.get("Content-Type", ""))
        self.assertLess(time.monotonic() - started, 3)
        for path in ("/app.js", "/styles.css"):
            self.assertEqual(self.request("GET", path, cookie=cookie)[0], 200)
            self.assertIn(self.request("GET", path)[0], (302, 303, 401))


if __name__ == "__main__":
    unittest.main()
