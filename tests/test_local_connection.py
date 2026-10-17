import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

from backend.local_connection import LocalConnection, validated_url
from backend.providers import GatewayError, ModelGateway, _direct_response


class LocalConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.connection = LocalConnection(self.root / "connection.bin")
        self.data = {"baseUrl": "https://api.example.org/v1", "apiKey": "test-only-not-a-real-secret", "model": "gemini-4-argon"}
        self.codex = Mock()
        self.codex.status.return_value = {"id": "gpt", "name": "GPT", "model": "gpt-6.1-sol", "configured": True, "source": "codex"}
        self.discovery = patch("backend.codex_provider.discover", return_value=self.codex)
        self.discovery.start()
        self.addCleanup(self.discovery.stop)

    def gateway(self):
        return ModelGateway(config_path=self.root / "config.toml", dotenv_path=self.root / ".env", env={},
                            connection_path=self.connection.path, catalog_path=self.root / "catalog.json")

    def test_url_validation(self):
        self.assertEqual(validated_url(" http://127.0.0.1:1234/v1/ "), "http://127.0.0.1:1234/v1")
        for value in ("http://example.org/v1", "https://user:pw@example.org/v1", "https://api.example.org/v1?key=x",
                      "https://api.example.org/#x", "https://api.example.org/%0d%0aAuthorization:x", "https://api.example.org\\@other.org/v1",
                      "https://api.example.org/../v1", "https://192.168.1.1/v1", "https://api.example.org:99999/v1",
                      "https://api.example.org/v1/chat/completions", "https://127.1/v1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validated_url(value)

    @unittest.skipUnless(os.name == "nt", "DPAPI is Windows-only")
    def test_dpapi_round_trip_and_address_bound_empty_key(self):
        self.connection.save(self.data)
        self.assertNotIn(self.data["apiKey"].encode(), self.connection.path.read_bytes())
        self.assertEqual(self.connection.load(), self.data)
        self.assertNotIn(self.data["apiKey"], json.dumps(self.connection.metadata()))
        self.connection.save({**self.data, "apiKey": ""})
        with self.assertRaises(ValueError):
            self.connection.prepare({"baseUrl": "https://other.example.org/v1", "apiKey": ""})
        self.connection.clear()
        self.assertFalse(self.connection.metadata()["hasKey"])

    def test_custom_connection_does_not_change_existing_routes(self):
        with patch.object(LocalConnection, "load", return_value=self.data):
            gateway = self.gateway()
        statuses = {item["id"]: item for item in gateway.status()}
        self.assertEqual(statuses["gpt"]["source"], "codex")
        self.assertTrue(statuses["custom"]["configured"])
        for provider in ("gemini", "deepseek", "grok"):
            self.assertFalse(statuses[provider]["configured"])
            self.assertEqual(gateway._key(provider, gateway._settings), "")
        self.assertNotIn(self.data["apiKey"], json.dumps(statuses))
        self.codex.respond.return_value = "GPT via Codex"
        self.assertEqual(gateway.respond("gpt", "hello"), "GPT via Codex")
        with patch("backend.providers._JsonProcess") as process:
            process.return_value.receive.return_value = {"content": [{"type": "text", "text": "custom response"}]}
            self.assertEqual(gateway.respond("custom", "hello"), "custom response")
        sent = process.return_value.send.call_args.args[0]
        self.assertEqual(sent["compatible_url"], self.data["baseUrl"])
        self.assertEqual(sent["provider"], "custom")
        self.assertNotIn(self.data["apiKey"], str(process.call_args))

    def test_catalog_appends_without_erasing_existing_choices(self):
        (self.root / "catalog.json").write_text(json.dumps([{"providerId": "custom", "model": "model:v2", "name": "我的连接"}]), encoding="utf-8")
        choices = {(item["providerId"], item["model"]) for item in self.gateway().model_options()}
        self.assertIn(("custom", "model:v2"), choices)
        self.assertIn(("gemini", "gemini-4-argon"), choices)
        self.assertIn(("grok", "grok-4.7"), choices)
        (self.root / "catalog.json").write_text(json.dumps([{"providerId": "custom", "model": "x", "name": "x", "apiKey": "never-display-me"}]), encoding="utf-8")
        with self.assertRaises(GatewayError) as error:
            self.gateway().model_options()
        self.assertNotIn("never-display-me", str(error.exception))

    def test_connection_test_does_not_save(self):
        with patch("backend.providers._direct_response", return_value="OK") as request:
            self.assertTrue(self.connection.test(self.data)["ok"])
        self.assertFalse(self.connection.path.exists())
        self.assertEqual(request.call_args.args[0]["provider"], "custom")

    def test_corrupt_configuration_is_a_safe_unconfigured_state(self):
        self.connection.path.write_bytes(b"invalid")
        self.assertFalse(self.connection.metadata()["hasKey"])
        self.assertFalse({item["id"]: item for item in self.gateway().status()}["custom"]["configured"])

    def test_real_local_transport_refuses_redirect_without_forwarding_key(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                requests.append(self.path)
                if self.path.startswith("/redirect/"):
                    self.send_response(307)
                    self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/capture")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = json.dumps({"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            data = {"provider": "custom", "model": "test", "prompt": "hello", "key": self.data["apiKey"],
                    "compatible_url": f"http://127.0.0.1:{server.server_port}/v1"}
            self.assertEqual(_direct_response(data), "OK")
            # Exercise the disposable provider child process too: it must load
            # its helper correctly when launched as backend/providers.py.
            with patch.object(LocalConnection, "load", return_value={
                    **self.data, "baseUrl": data["compatible_url"], "model": "test"}):
                gateway = self.gateway()
            self.assertEqual(gateway.respond("custom", "hello"), "OK")
            data["compatible_url"] = f"http://127.0.0.1:{server.server_port}/redirect"
            with self.assertRaises(GatewayError) as error:
                _direct_response(data)
            self.assertNotIn(self.data["apiKey"], str(error.exception))
            self.assertEqual(requests, ["/v1/chat/completions", "/v1/chat/completions", "/redirect/chat/completions"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
