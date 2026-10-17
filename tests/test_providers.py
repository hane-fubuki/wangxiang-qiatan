import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
import urllib.error

from backend.providers import (
    CancelledError, GatewayError, ModelGateway, _direct_response,
    _dotenv, _extract_text, _repair_deepseek_text, _safe_error, _mcp_arguments,
)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config.toml"
        self.codex = Mock()
        self.codex.status.return_value = {"id": "gpt", "name": "GPT", "configured": False, "model": "Codex", "source": "codex", "detail": "未登录"}
        discovery = patch("backend.codex_provider.discover", return_value=self.codex)
        self.discover = discovery.start()
        self.addCleanup(discovery.stop)

    def gateway(self, env=None, **kwargs):
        return ModelGateway(config_path=self.config, dotenv_path=self.root / ".env", env=env or {}, **kwargs)

    def fake_mcp(self, behavior="success", provider="deepseek"):
        script = self.root / "fake_mcp.py"
        script.write_text(
            "import json,sys,time\n"
            "for line in sys.stdin.buffer:\n"
            " r=json.loads(line)\n"
            " if r.get('method')=='initialize':\n"
            "  print(json.dumps({'id':r['id'],'result':{'protocolVersion':'2024-11-05'}}),flush=True)\n"
            " elif r.get('method')=='tools/call':\n"
            + {
                "success": "  print(json.dumps({'method':'notifications/progress','params':{}}),flush=True)\n  print(json.dumps({'id':r['id'],'result':{'content':[{'type':'text','text':r['params']['arguments']['prompt']}]}}),flush=True)\n",
                "model": "  print(json.dumps({'id':r['id'],'result':{'content':[{'type':'text','text':json.dumps(r['params'])}]}}),flush=True)\n",
                "wait": "  time.sleep(30)\n",
                "error": "  print(json.dumps({'id':r['id'],'result':{'isError':True,'content':[{'type':'text','text':'401 secret-key-MUST-NOT-LEAK'}]}}),flush=True)\n",
                "invalid": "  print('not json',flush=True)\n",
                "exit": "  sys.exit(1)\n",
            }[behavior], encoding="utf-8",
        )
        self.config.write_text(
            "[mcp_servers." + provider + "]\ncommand = " + json.dumps(sys.executable)
            + "\nargs = [" + json.dumps(str(script)) + "]\n", encoding="utf-8",
        )

    def test_unconfigured_status_does_not_claim_connection(self):
        self.assertTrue(all(not item["configured"] for item in self.gateway().status()))
        with self.assertRaisesRegex(GatewayError, "尚未配置"):
            self.gateway().respond("deepseek", "hi")

    def test_status_never_includes_keys(self):
        status = self.gateway({"GEMINI_API_KEY": "private-secret", "GEMINI_MODEL": "gemini-custom"}).status()
        self.assertNotIn("private-secret", json.dumps(status))
        self.assertEqual(status[1]["model"], "gemini-custom")
        self.assertEqual(status[1]["source"], "api")

    def test_grok_credentials_support_both_names_without_exposing_them(self):
        for name in ("GROK_API_KEY", "XAI_API_KEY"):
            with self.subTest(name=name):
                gateway = self.gateway({name: "private-grok-secret", "GROK_MODEL": "grok-custom"})
                status = {item["id"]: item for item in gateway.status()}["grok"]
                self.assertTrue(status["configured"])
                self.assertEqual((status["source"], status["model"]), ("api", "grok-custom"))
                self.assertNotIn("private-grok-secret", json.dumps(gateway.model_options()))

    def test_model_options_include_argon_and_deduplicate_configured_flash(self):
        gateway = self.gateway({"GEMINI_API_KEY": "fake", "GROK_MODEL": "grok-custom", "DEEPSEEK_MODEL": "deepseek-v4-pro"})
        options = gateway.model_options()
        self.assertEqual(len(options), len({(item["providerId"], item["model"]) for item in options}))
        models = {(item["providerId"], item["model"]): item for item in options}
        self.assertTrue(models[("gemini", "gemini-4-argon")]["configured"])
        self.assertTrue(models[("gemini", "gemini-3.8-flash")]["configured"])
        self.assertEqual(models[("deepseek", "deepseek-v4-pro")]["name"], "DeepSeek V4 Pro")
        self.assertFalse(models[("grok", "grok-custom")]["configured"])

    def test_grok_dotenv_supports_key_alias_and_model_without_interpolation(self):
        path = self.root / ".env"
        path.write_text("GROK_API_KEY=primary\nXAI_API_KEY='fallback'\nGROK_MODEL=grok-custom\nOTHER_SECRET=ignore\n", encoding="utf-8")
        self.assertEqual(_dotenv(path), {"GROK_API_KEY": "primary", "XAI_API_KEY": "fallback", "GROK_MODEL": "grok-custom"})

    def test_grok_mcp_discovery_uses_ask_grok_and_model_override(self):
        self.fake_mcp("model", provider="grok")
        gateway = self.gateway({"GROK_API_KEY": "unused-secret", "GROK_MODEL": "grok-custom"})
        self.assertEqual({item["id"]: item for item in gateway.status()}["grok"]["source"], "mcp")
        response = json.loads(gateway.respond("grok", "你好"))
        self.assertEqual(response["name"], "ask_grok")
        self.assertEqual(response["arguments"]["model"], "grok-custom")

    def test_grok_direct_fallback_prefers_primary_key_and_keeps_it_out_of_command(self):
        gateway = self.gateway({"GROK_API_KEY": "primary-fake", "XAI_API_KEY": "alias-fake", "GROK_MODEL": "grok-custom"})
        with patch("backend.providers._JsonProcess") as transport_type:
            transport = transport_type.return_value
            transport.receive.return_value = {"content": [{"type": "text", "text": "ok"}]}
            self.assertEqual(gateway.respond("grok", "hi"), "ok")
        payload = transport.send.call_args.args[0]
        self.assertEqual(payload["key"], "primary-fake")
        self.assertEqual((payload["provider"], payload["model"]), ("grok", "grok-custom"))
        self.assertNotIn("primary-fake", str(transport_type.call_args.args[0]))
        transport.close.assert_called_once()

    def test_assignments_change_provider_without_changing_persistent_character_slot(self):
        gateway = self.gateway({"GROK_API_KEY": "fake", "GROK_MODEL": "grok-custom"})
        assignments = {"gemini": {"providerId": "grok", "model": "grok-custom"}}
        status = {item["id"]: item for item in gateway.room_status("zzz-trio", assignments)}
        self.assertEqual((status["gemini"]["providerId"], status["gemini"]["model"], status["gemini"]["name"]), ("grok", "grok-custom", "Grok"))
        self.assertTrue(status["gemini"]["configured"])
        self.assertEqual(status["deepseek"]["model"], "gemini-4-argon")
        with patch.object(gateway, "respond", return_value="ok") as respond:
            cancel = threading.Event()
            self.assertEqual(gateway.respond_for("zzz-trio", "gemini", "hi", cancel, assignments), "ok")
            respond.assert_called_once_with("grok", "hi", cancel, model="grok-custom", reasoning_effort="medium")
        self.assertEqual(assignments, {"gemini": {"providerId": "grok", "model": "grok-custom"}})

    def test_invalid_assignments_never_start_transport_or_silently_discard_slots(self):
        gateway = self.gateway({"GROK_API_KEY": "fake", "GROK_MODEL": "grok-custom"})
        invalid = [[], {"missing": {"providerId": "grok", "model": "grok-custom"}},
                   {"gemini": None}, {"gemini": {"providerId": [], "model": "grok-custom"}},
                   {"gemini": {"providerId": "unknown", "model": "grok-custom"}},
                   {"gemini": {"providerId": "grok", "model": "../secret"}},
                   {"gemini": {"providerId": "grok", "model": "grok-not-selected"}},
                   {"gemini": {"providerId": "grok", "model": "gemini-4-argon"}},
                   {"gemini": {"providerId": "grok", "model": []}}]
        with patch("backend.providers._JsonProcess") as transport:
            for assignments in invalid:
                with self.subTest(assignments=assignments):
                    with self.assertRaises(GatewayError):
                        gateway.room_status("zzz-trio", assignments)
                    with self.assertRaises(GatewayError):
                        gateway.respond_for("zzz-trio", "deepseek", "hi", assignments=assignments)
            transport.assert_not_called()

    def test_room_status_uses_actual_transport_configuration_not_historical_slot(self):
        gateway = self.gateway({"GEMINI_API_KEY": "private-gemini-secret", "GEMINI_MODEL": "gemini-custom",
                                "DEEPSEEK_MODEL": "deepseek-v4-pro"})
        original = gateway.status()
        trio = {item["id"]: item for item in gateway.room_status("zzz-trio")}
        standard = {item["id"]: item for item in gateway.room_status("standard")}
        self.assertEqual(trio["deepseek"]["providerId"], "gemini")
        self.assertEqual(trio["deepseek"]["model"], "gemini-4-argon")
        self.assertTrue(trio["deepseek"]["configured"])
        self.assertEqual(trio["deepseek"]["source"], "api")
        self.assertEqual(trio["gemini"]["model"], "gemini-3.8-flash")
        self.assertFalse(standard["deepseek"]["configured"])
        self.assertEqual(standard["deepseek"]["model"], "deepseek-v4-pro")
        self.assertEqual(standard["gemini"]["model"], "gemini-custom")
        self.assertNotIn("private-gemini-secret", json.dumps(trio))
        trio["deepseek"]["detail"] = "mutated"
        self.assertEqual(gateway.status(), original)

    def test_nangong_is_unconfigured_when_only_deepseek_is_connected(self):
        gateway = self.gateway({"DEEPSEEK_API_KEY": "fake"})
        trio = {item["id"]: item for item in gateway.room_status("zzz-trio")}
        self.assertFalse(trio["deepseek"]["configured"])
        self.assertEqual(trio["deepseek"]["source"], "none")
        with self.assertRaisesRegex(GatewayError, "Gemini 尚未配置"):
            gateway.respond_for("zzz-trio", "deepseek", "hi")

    def test_character_and_standard_model_selection_reaches_mcp_arguments(self):
        self.fake_mcp("model", provider="gemini")
        gateway = self.gateway({"GEMINI_MODEL": "gemini-default"})
        for room, slot, model in (("zzz-trio", "deepseek", "gemini-4-argon"),
                                  ("zzz-trio", "gemini", "gemini-3.8-flash"),
                                  ("standard", "gemini", "gemini-default")):
            with self.subTest(room=room, slot=slot):
                result = json.loads(gateway.respond_for(room, slot, "中文路由测试"))
                self.assertEqual(result["name"], "ask_gemini")
                self.assertEqual(result["arguments"]["model"], model)
                self.assertEqual(result["arguments"]["prompt"], "中文路由测试")
        self.assertEqual(gateway.status()[1]["model"], "gemini-default")

    def test_standard_deepseek_keeps_project_v4_pro_and_can_override_one_call(self):
        self.fake_mcp("model")
        gateway = self.gateway({"DEEPSEEK_MODEL": "deepseek-v4-pro"})
        normal = json.loads(gateway.respond_for("standard", "deepseek", "hi"))
        override = json.loads(gateway.respond("deepseek", "hi", model="models/deepseek-test"))
        self.assertEqual(normal["arguments"]["model"], "deepseek-v4-pro")
        self.assertEqual(override["arguments"]["model"], "deepseek-test")
        self.assertEqual(gateway.status()[0]["model"], "deepseek-v4-pro")

    def test_argon_override_is_forwarded_to_direct_fallback(self):
        gateway = self.gateway({"GEMINI_API_KEY": "fake", "GEMINI_MODEL": "gemini-default"})
        cancel = threading.Event()
        with patch("backend.providers._JsonProcess") as transport_type:
            transport = transport_type.return_value
            transport.receive.return_value = {"content": [{"type": "text", "text": "ok"}]}
            self.assertEqual(gateway.respond_for("zzz-trio", "deepseek", "hi", cancel), "ok")
        payload = transport.send.call_args.args[0]
        self.assertEqual((payload["provider"], payload["model"]), ("gemini", "gemini-4-argon"))
        self.assertIs(transport.receive.call_args.args[1], cancel)
        transport.close.assert_called_once()

    def test_invalid_room_slot_model_and_precancel_never_start_transport(self):
        gateway = self.gateway({"GEMINI_API_KEY": "fake"})
        with patch("backend.providers._JsonProcess") as transport:
            for room, slot in (("missing", "deepseek"), ("zzz-trio", "missing")):
                with self.assertRaises(ValueError):
                    gateway.respond_for(room, slot, "hi")
            for model in ("", "../private", "gemini?secret=token", [], 123):
                with self.subTest(model=model), self.assertRaises(GatewayError):
                    gateway.respond("gemini", "hi", model=model)
            cancel = threading.Event()
            cancel.set()
            with self.assertRaises(CancelledError):
                gateway.respond_for("zzz-trio", "deepseek", "hi", cancel)
            transport.assert_not_called()

    def test_codex_model_override_uses_new_connection_without_mutating_defaults(self):
        from backend.codex_provider import CodexConnection
        connection = CodexConnection("fake-codex", True, "test", "gpt-6.1-sol", {})
        self.discover.return_value = connection
        gateway = self.gateway()
        cancel = threading.Event()
        with patch.object(CodexConnection, "respond", autospec=True, return_value="ok") as respond:
            self.assertEqual(gateway.respond("gpt", "hi", cancel, model="gpt-test"), "ok")
        called = respond.call_args.args
        self.assertEqual(called[0].model, "gpt-test")
        self.assertEqual(called[1:], ("hi", cancel, gateway.timeout))
        self.assertEqual(respond.call_args.kwargs, {"reasoning_effort": "medium"})
        self.assertEqual(gateway.status()[2]["model"], "gpt-6.1-sol")

    def test_gpt_uses_codex_instead_of_mcp_or_api(self):
        self.codex.respond.return_value = '{"speak":true,"to":"user","content":"你好"}'
        self.config.write_text('model="my-codex-model"\n[mcp_servers.gpt]\ncommand="must-not-run"\n', encoding="utf-8")
        gateway = self.gateway({"GPT_API_KEY": "must-not-use", "OPENAI_API_KEY": "must-not-use"})
        self.assertEqual(self.discover.call_args.kwargs["model"], "gpt-6.1-sol")
        cancel = threading.Event()
        with patch.object(gateway, "_respond_mcp") as mcp, patch("backend.providers._JsonProcess") as direct:
            self.assertEqual(gateway.respond("gpt", "你好", cancel), self.codex.respond.return_value)
            self.codex.respond.assert_called_once_with("你好", cancel, gateway.timeout, reasoning_effort="medium")
            mcp.assert_not_called()
            direct.assert_not_called()

    def test_codex_errors_and_cancellation_use_gateway_contract(self):
        from backend.codex_provider import CodexError, CodexCancelled
        gateway = self.gateway()
        for error, expected in ((CodexError("连接失败"), GatewayError), (CodexCancelled("已停止"), CancelledError)):
            self.codex.respond.side_effect = error
            with self.assertRaises(expected):
                gateway.respond("gpt", "你好")

    def test_dotenv_is_not_executed_and_env_takes_precedence(self):
        path = self.root / ".env"
        path.write_text("GEMINI_MODEL='gemini-file'\nGEMINI_API_KEY=example # comment\nUNRELATED=ignore\n", encoding="utf-8")
        self.assertEqual(_dotenv(path), {"GEMINI_MODEL": "gemini-file", "GEMINI_API_KEY": "example"})
        self.assertEqual(self.gateway({"GEMINI_MODEL": "gemini-env"}).status()[1]["model"], "gemini-env")

    def test_refresh_reloads_files_but_status_is_pure_read(self):
        gateway = self.gateway()
        self.fake_mcp()
        (self.root / ".env").write_text("DEEPSEEK_MODEL=deepseek-updated\n", encoding="utf-8")
        self.assertFalse(gateway.status()[0]["configured"])
        refreshed = gateway.refresh()
        self.assertTrue(refreshed[0]["configured"])
        self.assertEqual(refreshed[0]["model"], "deepseek-updated")

    def test_refresh_keeps_explicit_constructor_overrides(self):
        env = {"GEMINI_MODEL": "gemini-fixed"}
        gateway = self.gateway(env, timeout=12)
        env["GEMINI_MODEL"] = "gemini-changed-externally"
        (self.root / ".env").write_text("GEMINI_MODEL=gemini-file\nMODEL_TIMEOUT_SECONDS=150\n", encoding="utf-8")
        with patch.dict("os.environ", {"GEMINI_MODEL": "gemini-process"}):
            gateway.refresh()
        self.assertEqual(gateway.status()[1]["model"], "gemini-fixed")
        self.assertEqual(gateway.timeout, 12)

    def test_refresh_does_not_change_an_inflight_call(self):
        self.fake_mcp()
        gateway = self.gateway()
        started, proceed = threading.Event(), threading.Event()
        results = []
        def delayed(provider, model, prompt, server, cancel, deadline, reasoning_effort):
            started.set()
            proceed.wait(2)
            return model
        with patch.object(gateway, "_respond_mcp", side_effect=delayed):
            worker = threading.Thread(target=lambda: results.append(gateway.respond("deepseek", "hi")))
            worker.start()
            self.assertTrue(started.wait(2))
            (self.root / ".env").write_text("DEEPSEEK_MODEL=deepseek-new\n", encoding="utf-8")
            gateway.refresh()
            proceed.set()
            worker.join(2)
        self.assertEqual(results, ["deepseek-flash"])
        self.assertEqual(gateway.status()[0]["model"], "deepseek-new")

    def test_mcp_round_trip_unicode_and_notifications(self):
        self.fake_mcp()
        gateway = self.gateway()
        self.assertEqual(gateway.status()[0]["source"], "mcp")
        self.assertEqual(gateway.respond("deepseek", "你好\n共同讨论"), "你好\n共同讨论")

    def test_mcp_errors_are_sanitized(self):
        self.fake_mcp("error")
        with self.assertRaises(GatewayError) as caught:
            self.gateway().respond("deepseek", "你好")
        self.assertIn("身份验证", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))

    def test_timeout_terminates_subprocess(self):
        self.fake_mcp("wait")
        start = time.monotonic()
        with self.assertRaisesRegex(GatewayError, "超时"):
            self.gateway(timeout=0.3).respond("deepseek", "wait")
        self.assertLess(time.monotonic() - start, 3)

    def test_cancellation_terminates_subprocess(self):
        self.fake_mcp("wait")
        cancel = threading.Event()
        timer = threading.Timer(0.3, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        start = time.monotonic()
        with self.assertRaises(CancelledError):
            self.gateway(timeout=30).respond("deepseek", "wait", cancel)
        self.assertLess(time.monotonic() - start, 3)

    def test_precancel_never_starts_a_process(self):
        cancel = threading.Event()
        cancel.set()
        with patch("backend.providers.subprocess.Popen") as popen:
            with self.assertRaises(CancelledError):
                self.gateway().respond("deepseek", "hi", cancel)
            popen.assert_not_called()

    def test_invalid_mcp_output_has_safe_error(self):
        self.fake_mcp("invalid")
        with self.assertRaisesRegex(GatewayError, "JSON"):
            self.gateway().respond("deepseek", "hi")

    def test_mcp_unexpected_exit_has_safe_error(self):
        self.fake_mcp("exit")
        with self.assertRaisesRegex(GatewayError, "退出"):
            self.gateway().respond("deepseek", "hi")

    def test_disabled_mcp_uses_environment_fallback(self):
        self.config.write_text('[mcp_servers.deepseek]\ncommand="missing.exe"\nenabled=false\n', encoding="utf-8")
        self.assertEqual(self.gateway({"DEEPSEEK_API_KEY": "fake"}).status()[0]["source"], "api")

    def test_malformed_config_is_not_exposed(self):
        self.config.write_text("SECRET=something invalid", encoding="utf-8")
        status = self.gateway().status()
        self.assertFalse(status[0]["configured"])
        self.assertNotIn("SECRET", str(status))

    def test_text_blocks_are_combined_and_empty_output_fails(self):
        self.assertEqual(_extract_text({"content": [{"type": "text", "text": "a"}, {"type": "image"}, {"type": "text", "text": "b"}]}), "a\nb")
        with self.assertRaisesRegex(GatewayError, "没有返回文本"):
            _extract_text({"content": []})

    def test_error_classification_does_not_echo_secrets(self):
        for raw in ("secret 429", "secret 404", "secret 503", "secret unknown", "secret timeout"):
            self.assertNotIn("secret", _safe_error(raw))

    def test_direct_safe_errors_survive_process_boundary(self):
        safe = _safe_error("401")
        with self.assertRaises(GatewayError) as caught:
            _extract_text({"isError": True, "content": [{"type": "text", "text": safe}]})
        self.assertEqual(str(caught.exception), safe)

    def test_deepseek_latin1_mojibake_is_repaired_reversibly(self):
        expected = '{"speak": true, "content": "周末室内活动，中文与 English 😀"}'
        corrupted = expected.encode("utf-8").decode("latin-1")
        self.assertEqual(_repair_deepseek_text(corrupted), expected)

    def test_deepseek_unicode_and_accented_text_are_preserved(self):
        for text in ("中文与 English 😀", "café, déjà vu", "normal ASCII", "中文与 café 混合 Unicode", "invalid \xff bytes"):
            with self.subTest(text=text):
                self.assertEqual(_repair_deepseek_text(text), text)

    def test_direct_gemini_discards_thought_parts_and_uses_header_key(self):
        response = {"candidates": [{"content": {"parts": [{"thought": True, "text": "private reasoning"}, {"text": "visible answer"}]}}]}
        with patch("backend.providers.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as fetch:
            result = _direct_response({"provider": "gemini", "model": "gemini-test", "prompt": "你好", "key": "fake-key"})
        self.assertEqual(result, "visible answer")
        request = fetch.call_args.args[0]
        self.assertNotIn("fake-key", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "fake-key")

    def test_direct_deepseek_parses_content(self):
        response = {"choices": [{"message": {"content": "回答"}}]}
        with patch("backend.providers.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
            self.assertEqual(_direct_response({"provider": "deepseek", "model": "deepseek-test", "prompt": "你好", "key": "fake"}), "回答")

    def test_direct_grok_uses_official_endpoint_auth_and_visible_content(self):
        response = {"choices": [{"message": {"content": "回答", "reasoning_content": "private reasoning"}}]}
        with patch("backend.providers.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as fetch:
            self.assertEqual(_direct_response({"provider": "grok", "model": "grok-test", "prompt": "你好", "key": "fake-key"}), "回答")
        request = fetch.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.x.ai/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer fake-key")
        self.assertNotIn("fake-key", request.full_url)
        body = json.loads(request.data)
        self.assertEqual(body["messages"], [{"role": "user", "content": "你好"}])
        self.assertEqual(body["model"], "grok-test")
        self.assertNotIn("thinking", body)
        self.assertNotIn("response_format", body)

    def test_direct_grok_rejects_malformed_or_empty_content_and_sanitizes_errors(self):
        for response in ({}, {"choices": []}, {"choices": [{"message": {"content": None}}]}):
            with self.subTest(response=response), patch("backend.providers.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
                with self.assertRaises(GatewayError):
                    _direct_response({"provider": "grok", "model": "grok-test", "prompt": "hi", "key": "fake"})
        error = urllib.error.HTTPError("https://api.x.ai/v1/chat/completions", 401, "private-secret", {}, None)
        with patch("backend.providers.urllib.request.urlopen", side_effect=error), self.assertRaises(GatewayError) as caught:
            _direct_response({"provider": "grok", "model": "grok-test", "prompt": "hi", "key": "fake"})
        self.assertIn("身份验证", str(caught.exception))
        self.assertNotIn("private-secret", str(caught.exception))

    def test_rest_json_mode_uses_official_provider_fields(self):
        responses = {
            "deepseek": {"choices": [{"message": {"content": '{"speak":false}'}}]},
            "grok": {"choices": [{"message": {"content": '{"speak":false}'}}]},
            "gemini": {"candidates": [{"content": {"parts": [{"text": '{"speak":false}'}]}}]},
        }
        for provider, response in responses.items():
            with self.subTest(provider=provider):
                with patch("backend.providers.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as fetch:
                    _direct_response({"provider": provider, "model": provider + "-test", "prompt": "JSON", "key": "fake", "json_mode": True})
                body = json.loads(fetch.call_args.args[0].data)
                if provider in ("deepseek", "grok"):
                    self.assertEqual(body["response_format"], {"type": "json_object"})
                else:
                    self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")

    def test_direct_http_error_is_sanitized(self):
        error = urllib.error.HTTPError("https://example.invalid", 401, "private-secret", {}, None)
        with patch("backend.providers.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(GatewayError) as caught:
                _direct_response({"provider": "deepseek", "model": "deepseek-test", "prompt": "你好", "key": "fake"})
        self.assertIn("身份验证", str(caught.exception))
        self.assertNotIn("private-secret", str(caught.exception))

    def test_reasoning_choice_validates_before_start_and_follows_character_assignment(self):
        gateway = self.gateway({"GEMINI_API_KEY": "fake"})
        self.assertIs(gateway.supports_reasoning_options, True)
        with patch("backend.providers._JsonProcess") as transport:
            for effort in (None, "ultra", "none", "", [], True):
                with self.subTest(effort=effort), self.assertRaises(GatewayError):
                    gateway.respond("gemini", "hi", reasoning_effort=effort)
            transport.assert_not_called()
        with patch.object(gateway, "respond", return_value="ok") as respond:
            gateway.respond_for("zzz-trio", "deepseek", "hi", reasoning_effort="high")
            self.assertEqual(respond.call_args.kwargs, {"model": "gemini-4-argon", "reasoning_effort": "high"})

    def test_known_rest_models_use_supported_reasoning_and_larger_bounded_budgets(self):
        cases = [
            ("deepseek", "deepseek-v4-pro", "medium", {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}),
            ("deepseek", "deepseek-flash", "high", {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}),
            ("grok", "grok-4.7", "medium", {"reasoning_effort": "medium"}),
            ("grok", "grok-4.7", "high", {"reasoning_effort": "high"}),
            ("gemini", "gemini-4-argon", "high", {"thinkingLevel": "high", "includeThoughts": False}),
            ("gemini", "gemini-3.8-flash", "medium", {"thinkingLevel": "medium", "includeThoughts": False}),
            ("gemini", "gemini-2.5-pro", "high", {"thinkingBudget": 8192, "includeThoughts": False}),
        ]
        for provider, model, effort, fields in cases:
            with self.subTest(model=model, effort=effort):
                response = ({"candidates": [{"content": {"parts": [{"thought": True, "text": "private reasoning"}, {"text": "answer"}]}}]}
                            if provider == "gemini" else {"choices": [{"message": {"content": "answer", "reasoning_content": "private reasoning"}}]})
                with patch("backend.providers.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as fetch:
                    self.assertEqual(_direct_response({"provider": provider, "model": model, "prompt": "hi", "key": "fake", "reasoning_effort": effort}), "answer")
                body = json.loads(fetch.call_args.args[0].data)
                if provider == "gemini":
                    self.assertEqual(body["generationConfig"]["thinkingConfig"], fields)
                    budget = body["generationConfig"]["maxOutputTokens"]
                else:
                    for key, value in fields.items():
                        self.assertEqual(body[key], value)
                    budget = body["max_tokens"]
                self.assertEqual(budget, 32768 if effort == "high" else 16384)

    def test_unknown_models_do_not_receive_speculative_thinking_parameters(self):
        for provider in ("deepseek", "gemini", "grok"):
            response = ({"candidates": [{"content": {"parts": [{"text": "answer"}]}}]}
                        if provider == "gemini" else {"choices": [{"message": {"content": "answer"}}]})
            with self.subTest(provider=provider), patch("backend.providers.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as fetch:
                _direct_response({"provider": provider, "model": provider + "-custom", "prompt": "hi", "key": "fake", "reasoning_effort": "high"})
                body = json.loads(fetch.call_args.args[0].data)
                self.assertNotIn("reasoning_effort", body)
                self.assertNotIn("thinking", body)
                self.assertNotIn("thinkingConfig", body.get("generationConfig", {}))

    def test_mcp_schema_negotiates_reasoning_and_respects_bridge_token_limit(self):
        schema = {"properties": {"max_output_tokens": {"type": "integer", "maximum": 20000},
                                 "reasoning_effort": {"type": "string", "enum": ["medium", "high"]}}}
        args = _mcp_arguments("gemini", "gemini-4-argon", "hi", "high", schema)
        self.assertEqual((args["reasoning_effort"], args["max_output_tokens"]), ("high", 20000))
        for legacy in (None, {}, {"properties": {"reasoning_effort": {"type": "string", "enum": ["low"]}}}):
            self.assertNotIn("reasoning_effort", _mcp_arguments("gemini", "gemini-4-argon", "hi", "high", legacy))
        self.assertNotIn("reasoning_effort", _mcp_arguments("grok", "grok-custom", "hi", "high", schema))

    def test_mcp_lists_schema_and_only_adds_advertised_options(self):
        self.fake_mcp("model", provider="gemini")
        gateway = self.gateway()
        schema = {"properties": {"max_output_tokens": {"type": "integer", "maximum": 32768},
                                 "reasoning_effort": {"type": "string", "enum": ["medium", "high"]}}}
        with patch("backend.providers._JsonProcess") as process:
            transport = process.return_value
            transport.receive.side_effect = [
                {"capabilities": {"tools": {}}},
                {"tools": [{"name": "ask_gemini", "inputSchema": schema}]},
                {"content": [{"type": "text", "text": "answer"}]},
            ]
            self.assertEqual(gateway.respond("gemini", "hi", model="gemini-4-argon", reasoning_effort="high"), "answer")
            sent = [call.args[0] for call in transport.send.call_args_list]
            self.assertEqual([call["method"] for call in sent], ["initialize", "notifications/initialized", "tools/list", "tools/call"])
            self.assertEqual(sent[-1]["params"]["arguments"]["reasoning_effort"], "high")
            self.assertEqual(sent[-1]["params"]["arguments"]["max_output_tokens"], 32768)
            transport.close.assert_called_once()

    def test_mcp_legacy_schema_failure_does_not_fail_chat_or_leak_optional_parameters(self):
        self.fake_mcp(provider="deepseek")
        with patch("backend.providers._JsonProcess") as process:
            transport = process.return_value
            transport.receive.side_effect = [{"capabilities": {"tools": {}}}, GatewayError("unknown method"),
                                             {"content": [{"type": "text", "text": "answer"}]}]
            self.assertEqual(self.gateway().respond("deepseek", "hi", reasoning_effort="high"), "answer")
            arguments = transport.send.call_args.args[0]["params"]["arguments"]
            self.assertEqual(arguments, {"prompt": "hi", "model": "deepseek-flash", "max_output_tokens": 4096})

    def test_cancel_during_mcp_negotiation_never_sends_model_call(self):
        self.fake_mcp(provider="deepseek")
        with patch("backend.providers._JsonProcess") as process:
            transport = process.return_value
            transport.receive.side_effect = [{"capabilities": {"tools": {}}}, CancelledError("已停止")]
            with self.assertRaises(CancelledError):
                self.gateway().respond("deepseek", "hi")
            self.assertNotIn("tools/call", [call.args[0]["method"] for call in transport.send.call_args_list])
            transport.close.assert_called_once()

    def test_exhausted_thinking_budget_has_specific_safe_error_and_never_reveals_thought(self):
        for provider in ("deepseek", "gemini", "grok"):
            response = ({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"thought": True, "text": "private reasoning"}]}}]}
                        if provider == "gemini" else {"choices": [{"finish_reason": "length", "message": {"content": "", "reasoning_content": "private reasoning"}}]})
            with self.subTest(provider=provider), patch("backend.providers.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
                with self.assertRaisesRegex(GatewayError, "长度上限") as caught:
                    _direct_response({"provider": provider, "model": provider + "-custom", "prompt": "hi", "key": "fake"})
                self.assertNotIn("private", str(caught.exception))
                self.assertEqual(_safe_error(str(caught.exception)), str(caught.exception))


if __name__ == "__main__":
    unittest.main()
