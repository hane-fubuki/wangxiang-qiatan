"""HTTP boundary checks against a real loopback server and fake model transport."""
import http.client
import hashlib
import json
import tempfile
import threading
import unittest
from unittest.mock import patch

import remote
from app import create_server
from backend.providers import GatewayError
from backend.store import make_message


class FakeGateway:
    def status(self):
        return [{"id": provider, "name": provider, "configured": True} for provider in ("deepseek", "gemini", "gpt")]

    def respond(self, provider, prompt, cancel):
        return json.dumps({"speak": True, "to": "user", "content": provider + " 已收到问题"})


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = create_server(port=0, data_dir=cls.temp.name, gateway=FakeGateway())
        # Timing is covered separately; retain the real run cancellation boundary.
        engine = cls.server.engine
        reply_clock = patch.object(engine, "_wait_for_reply", side_effect=lambda run, provider: engine._current(run))
        reply_clock.start()
        cls.addClassCleanup(reply_clock.stop)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.engine.stop_all()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temp.cleanup()

    def request(self, method, path, payload=None, headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        data = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        request_headers = {"Content-Type": "application/json"} if data is not None else {}
        request_headers.update(headers or {})
        try:
            connection.request(method, path, data, request_headers)
            response = connection.getresponse()
            body = response.read()
            parsed = json.loads(body) if response.getheader("Content-Type", "").startswith("application/json") else body
            return response.status, parsed, dict(response.getheaders())
        finally:
            connection.close()

    def create(self):
        status, conversation, _ = self.request("POST", "/api/conversations", {})
        self.assertEqual(status, 201)
        return conversation["id"]

    def test_health_and_bootstrap(self):
        status, payload, headers = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["app"], "妄想洽谈中")
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, payload, _ = self.request("GET", "/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertEqual({p["id"] for p in payload["providers"]}, {"deepseek", "gemini", "gpt"})
        rooms = {room["id"]: room for room in payload["rooms"]}
        self.assertEqual(set(rooms), {"standard", "zzz-trio", "wangsheng-trio", "zzz-krampus", "zzz-yunkui", "zzz-obol", "zzz-mockingbird", "zzz-outer-ring", "zzz-roscaelifer"})
        self.assertEqual(rooms["zzz-trio"]["category"], "酒馆")
        self.assertEqual({key: value["name"] for key, value in rooms["zzz-trio"]["characters"].items()},
                         {"gemini": "千夏", "deepseek": "南宫羽", "gpt": "爱芮", "belle": "铃"})
        expected_starters = {"standard": [("ideas", "lightbulb"), ("learn", "book"), ("compare", "compare")],
                             "zzz-trio": [("meet", "coffee"), ("song", "music"), ("dayoff", "sun")]}
        for room_id, expected in expected_starters.items():
            self.assertEqual([(item["id"], item["icon"]) for item in rooms[room_id]["starters"]], expected)

    def test_remote_launcher_recognizes_renamed_service(self):
        with patch.object(remote, "APP_PORT", self.server.server_port):
            self.assertTrue(remote.health(self.server.server_port))

    def test_model_options_are_exposed_on_bootstrap_and_refresh(self):
        options = [{"providerId": "grok", "model": "grok-4.7", "name": "Grok 4.7", "configured": True}]
        with patch.object(self.server.engine.gateway, "model_options", return_value=options, create=True):
            for method, path, payload in (("GET", "/api/bootstrap", None), ("POST", "/api/providers/refresh", {})):
                with self.subTest(path=path):
                    status, result, _ = self.request(method, path, payload)
                    self.assertEqual(status, 200)
                    self.assertEqual(result["modelOptions"], options)

    def test_model_assignment_patch_is_validated_before_any_persistence(self):
        cid = self.create()
        path = "/api/conversations/" + cid
        before = self.server.store.get(cid)
        with patch.object(self.server.engine, "room_status", side_effect=GatewayError("该模型不在当前可选列表中")):
            status, _, _ = self.request("PATCH", path, {"title": "不应保存", "settings": {
                "models": {"gemini": {"providerId": "grok", "model": "invalid-model"}}}})
        self.assertEqual(status, 503)
        self.assertEqual(self.server.store.get(cid), before)

    def test_bootstrap_only_advertises_user_avatar_when_the_file_exists(self):
        for exists in (False, True):
            with self.subTest(exists=exists), patch("app.Path.is_file", return_value=exists), patch("app.Path.read_bytes", return_value=b"avatar"):
                status, payload, _ = self.request("GET", "/api/bootstrap")
                self.assertEqual(status, 200)
                version = hashlib.sha256(b"avatar").hexdigest()[:16]
                self.assertEqual(payload["userProfile"], {"name": "你", "avatar": f"/assets/user-avatar.png?v={version}" if exists else None})

    def test_avatar_replacement_changes_url_and_serves_current_bytes(self):
        urls = []
        for image in (b"old-avatar", b"new-avatar", b"new-avatar"):
            with patch("app.Path.is_file", return_value=True), patch("app.Path.read_bytes", return_value=image):
                status, bootstrap, _ = self.request("GET", "/api/bootstrap")
                self.assertEqual(status, 200)
                url = bootstrap["userProfile"]["avatar"]
                urls.append(url)
                status, payload, headers = self.request("GET", url)
                self.assertEqual(status, 200)
                self.assertEqual(payload, image)
                self.assertEqual(headers["Content-Type"], "image/png")
        self.assertNotEqual(urls[0], urls[1])
        self.assertEqual(urls[1], urls[2])

    def test_starter_generation_routes_request_without_creating_chat_or_messages(self):
        before = self.server.store.list()
        runs_before = self.server.engine.snapshot()
        result = {"roomId": "zzz-trio", "starterId": "song", "provider": "gemini", "prompt": "如果把雨声写成一首歌，你们会怎样编排？"}
        with patch.object(self.server.starters, "generate", return_value=result) as generate:
            status, payload, _ = self.request("POST", "/api/starters/generate", {"roomId": "zzz-trio", "starterId": "song"})
        self.assertEqual(status, 200)
        self.assertEqual(payload, result)
        generate.assert_called_once_with("zzz-trio", "song")
        self.assertEqual(self.server.store.list(), before)
        self.assertEqual(self.server.engine.snapshot(), runs_before)

    def test_starter_generation_defaults_to_standard_room(self):
        result = {"roomId": "standard", "starterId": "ideas", "provider": "deepseek", "prompt": "怎样把一个小想法变成可执行的计划？"}
        with patch.object(self.server.starters, "generate", return_value=result) as generate:
            status, payload, _ = self.request("POST", "/api/starters/generate", {"starterId": "ideas"})
        self.assertEqual(status, 200)
        self.assertEqual(payload, result)
        generate.assert_called_once_with("standard", "ideas")

    def test_starter_generation_model_failure_returns_safe_503_without_chat_mutation(self):
        before = self.server.store.list()
        error = "模型服务暂时不可用，请稍后重试。"
        with patch.object(self.server.starters, "generate", side_effect=GatewayError(error)):
            status, payload, _ = self.request("POST", "/api/starters/generate", {"roomId": "standard", "starterId": "ideas"})
        self.assertEqual(status, 503)
        self.assertEqual(payload, {"error": error})
        self.assertEqual(self.server.store.list(), before)

    def test_starter_generation_rejects_missing_or_invalid_selection_before_model_call(self):
        before = self.server.store.list()
        payloads = ({}, {"roomId": "zzz-trio"}, {"starterId": None}, {"starterId": 3},
                    {"starterId": "unknown"}, {"roomId": "standard", "starterId": "meet"},
                    {"roomId": "missing", "starterId": "ideas"}, {"roomId": None, "starterId": "ideas"})
        with patch.object(self.server.starters.gateway, "respond") as respond:
            for payload in payloads:
                with self.subTest(payload=payload):
                    status, result, _ = self.request("POST", "/api/starters/generate", payload)
                    self.assertEqual(status, 400)
                    self.assertIn("error", result)
            respond.assert_not_called()
        self.assertEqual(self.server.store.list(), before)

    def test_room_creation_defaults_and_immutable_room_history(self):
        cid = self.create()
        self.assertEqual(self.request("GET", f"/api/conversations/{cid}")[1]["roomId"], "standard")
        status, roleplay, _ = self.request("POST", "/api/conversations", {"roomId": "zzz-trio"})
        self.assertEqual(status, 201)
        self.assertEqual(roleplay["roomId"], "zzz-trio")
        role_path = "/api/conversations/" + roleplay["id"]
        self.assertEqual(self.request("PATCH", role_path, {"roomId": "standard", "title": "must not apply"})[0], 400)
        self.assertEqual(self.request("GET", role_path)[1], roleplay)
        for invalid in ("unknown", None, [], 1):
            with self.subTest(room=invalid):
                self.assertEqual(self.request("POST", "/api/conversations", {"roomId": invalid})[0], 400)

    def test_create_update_read_delete(self):
        cid = self.create()
        status, payload, _ = self.request("PATCH", "/api/conversations/" + cid, {"title": "圆桌", "settings": {"maxRounds": 2}})
        self.assertEqual(status, 200)
        self.assertEqual(payload["title"], "圆桌")
        status, payload, _ = self.request("GET", "/api/conversations/" + cid)
        self.assertEqual(payload["settings"]["maxRounds"], 2)
        self.assertEqual(self.request("DELETE", "/api/conversations/" + cid)[0], 200)
        self.assertEqual(self.request("GET", "/api/conversations/" + cid)[0], 404)

    def test_invalid_settings_do_not_change_conversation(self):
        cid = self.create()
        for settings in ({"maxRounds": 0}, {"maxRounds": 9}, {"maxRounds": True}, {"participants": []},
                         {"participants": ["unknown"]}, {"mode": "invalid"}, []):
            with self.subTest(settings=settings):
                self.assertEqual(self.request("PATCH", "/api/conversations/" + cid, {"settings": settings})[0], 400)
        self.assertEqual(self.request("GET", "/api/conversations/" + cid)[1]["settings"]["maxRounds"], 3)

    def test_message_endpoint_rejects_null_and_invalid_contents(self):
        cid = self.create()
        self.server.store.append(cid, make_message("user", "已有问题"))
        for content in (None, "", "  ", 12, [], "a" * 12001):
            with self.subTest(content_type=type(content).__name__):
                self.assertEqual(self.request("POST", f"/api/conversations/{cid}/messages", {"content": content})[0], 400)

    def test_continue_requires_a_user_question(self):
        cid = self.create()
        self.assertEqual(self.request("POST", f"/api/conversations/{cid}/continue", {})[0], 400)

    def test_cross_origin_and_untrusted_host_are_rejected(self):
        before = len(self.server.store.list())
        for headers in ({"Origin": "https://malicious.example"}, {"Origin": "null"},
                        {"Host": "malicious.example"}, {"Host": "localhost:123"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request("POST", "/api/conversations", {}, headers=headers)[0], 403)
                self.assertEqual(self.request("GET", "/api/bootstrap", headers=headers)[0], 403)
        self.assertEqual(len(self.server.store.list()), before)
        origin = f"http://localhost:{self.server.server_port}"
        self.assertEqual(self.request("GET", "/api/health", headers={"Origin": origin})[0], 200)

    def test_static_allowlist_cannot_serve_source_credentials_or_history(self):
        for path in ("/.env", "/app.py", "/backend/providers.py", "/.tavern/conversations.json", "/../app.py",
                     "/%2e%2e/app.py", "/web/../.env", "/api/unknown", "/assets/PROMPTS.md",
                     "/assets/source.png", "/assets/deepseek-stand.svg", "/assets/gpt-avatar.png/../PROMPTS.md",
                     "/backend/rooms.py", "/backend/starters.py", "/assets/ZZZ-ASSETS.md", "/assets/zzz-sunna-turnaround.png",
                     "/assets/USER-AVATAR-PROMPT.md", "/assets/user-avatar-original.png"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 404)

    def test_character_images_are_allowed_without_opening_the_assets_directory(self):
        # Mock only file reads: no generated art is replaced or written by tests.
        payload = b"mock-image-bytes"
        with patch("app.Path.is_file", return_value=True), patch("app.Path.read_bytes", return_value=payload):
            for provider in ("deepseek", "gemini", "gpt", "grok"):
                for suffix in ("stand.png", "avatar.png", "original.jpg", "avatar-reference.png"):
                    with self.subTest(provider=provider, suffix=suffix):
                        status, body, headers = self.request("GET", f"/assets/{provider}-{suffix}")
                        self.assertEqual(status, 200)
                        self.assertEqual(body, payload)
                        self.assertEqual(headers["Content-Type"], "image/jpeg" if suffix.endswith("jpg") else "image/png")
                        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            for character in ("sunna", "nangong-yu", "aria"):
                for kind in ("stand", "avatar"):
                    status, body, headers = self.request("GET", f"/assets/zzz-{character}-{kind}.png")
                    self.assertEqual(status, 200)
                    self.assertEqual(body, payload)
                    self.assertEqual(headers["Content-Type"], "image/png")
            status, body, headers = self.request("GET", "/assets/user-avatar.png")
            self.assertEqual(status, 200)
            self.assertEqual(body, payload)
            self.assertEqual(headers["Content-Type"], "image/png")
            # These remain denied even when the requested source file exists.
            for path in ("/assets/PROMPTS.md", "/assets/source.png", "/assets/source.psd", "/assets/../app.js",
                         "/assets/USER-AVATAR-PROMPT.md", "/assets/user-avatar-original.png"):
                with self.subTest(private_path=path):
                    self.assertEqual(self.request("GET", path)[0], 404)

    def test_tea_theme_files_are_allowed_without_exposing_source_variants(self):
        payload = b"mock-theme-asset"
        with patch("app.Path.is_file", return_value=True), patch("app.Path.read_bytes", return_value=payload):
            for path, mime in (("/tea-theme.css", "text/css; charset=utf-8"),
                               ("/assets/tea-party-reference.jpg", "image/jpeg")):
                with self.subTest(path=path):
                    status, body, headers = self.request("GET", path)
                    self.assertEqual(status, 200)
                    self.assertEqual(body, payload)
                    self.assertEqual(headers["Content-Type"], mime)
                    self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            for path in ("/tea-theme.css.bak", "/assets/tea-party-reference-original.jpg"):
                with self.subTest(private_path=path):
                    self.assertEqual(self.request("GET", path)[0], 404)

    def test_bodyless_actions_accept_an_empty_json_object(self):
        for path in ("/api/providers/refresh", "/api/runs/" + "0" * 32 + "/stop"):
            with self.subTest(path=path):
                self.assertEqual(self.request("POST", path, {})[0], 404 if path.startswith('/api/runs/') else 200)
                self.assertEqual(self.request("POST", path, raw=b"")[0], 400)

    def test_json_only_and_malformed_payloads(self):
        self.assertEqual(self.request("POST", "/api/conversations", raw=b"{}", headers={"Content-Type": "text/plain"})[0], 400)
        for raw in (b"[]", b"{broken", b"\xff", b"", b" " * 131073):
            with self.subTest(size=len(raw)):
                self.assertEqual(self.request("POST", "/api/conversations", raw=raw)[0], 400)

    def test_chat_returns_real_transport_responses_and_stores_them(self):
        cid = self.create()
        status, payload, _ = self.request("POST", f"/api/conversations/{cid}/messages",
                                          {"content": "你好", "settings": {"maxRounds": 1}})
        self.assertEqual(status, 200)
        self.assertIn("runId", payload)
        finished = threading.Event()

        def await_finished():
            for _ in range(200):
                if cid not in self.server.engine.snapshot():
                    finished.set()
                    return
                threading.Event().wait(0.01)

        waiter = threading.Thread(target=await_finished, daemon=True)
        waiter.start()
        self.assertTrue(finished.wait(timeout=3))
        status, conversation, _ = self.request("GET", "/api/conversations/" + cid)
        self.assertEqual(status, 200)
        replies = [m for m in conversation["messages"] if m["role"] == "assistant"]
        self.assertEqual({m["provider"] for m in replies}, {"deepseek", "gemini", "gpt"})
        self.assertEqual({m["content"] for m in replies}, {"deepseek 已收到问题", "gemini 已收到问题", "gpt 已收到问题"})


if __name__ == "__main__":
    unittest.main()
