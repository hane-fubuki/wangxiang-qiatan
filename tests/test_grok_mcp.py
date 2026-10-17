"""Exercise the actual stdio bridge with local credential/network test doubles.

No test imports the installed credential or makes an HTTP request. PowerShell
functions shadow both commands before the unmodified bridge is dot-sourced.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")
BRIDGE = Path(__file__).resolve().parents[1] / "integrations" / "grok" / "grok-mcp.ps1"
SECRET = "protocol-test-secret-must-not-escape"


@unittest.skipUnless(POWERSHELL, "PowerShell is not installed")
class GrokMcpTests(unittest.TestCase):
    def run_protocol(self, requests, mode="success"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = root / "network-test-double.log"
            wrapper = root / "fixture.ps1"
            script_path = str(BRIDGE).replace("'", "''")
            wrapper.write_text(r'''
function Import-Clixml {
    param($LiteralPath)
    if ($env:TAVERN_GROK_TEST_MODE -eq 'credential-error') { throw 'credential-private-diagnostic' }
    $stub = [pscustomobject]@{}
    $stub | Add-Member -MemberType ScriptMethod -Name GetNetworkCredential -Value { return [pscustomobject]@{ Password = 'protocol-test-secret-must-not-escape' } }
    return $stub
}
function Invoke-RestMethod { throw 'Unexpected native REST call.' }
function Invoke-WebRequest {
    param($Uri, $Headers, $TimeoutSec, $MaximumRedirection, $Method, $ContentType, $Body, [switch]$UseBasicParsing)
    [IO.File]::AppendAllText($env:TAVERN_GROK_TEST_JOURNAL, "called`n")
    if ($env:TAVERN_GROK_TEST_MODE -eq 'network-error') { throw 'network-private-diagnostic' }
    if ($Uri -notin @('https://api.x.ai/v1/models', 'https://api.x.ai/v1/chat/completions')) { throw 'unexpected URI' }
    if ($Headers.Authorization -ne 'Bearer protocol-test-secret-must-not-escape') { throw 'wrong auth header' }
    if ($MaximumRedirection -ne 0) { throw 'redirects must stay disabled' }
    if ($Uri.EndsWith('/models')) {
        $response = @{ data = @(@{ id = 'grok-test-one'; internal = 'must-not-list' }, @{ id = 'grok-test-two' }) }
    } else {
        if ($Method -ne 'Post' -or $ContentType -ne 'application/json; charset=utf-8') { throw 'wrong request encoding' }
        $text = [Text.Encoding]::UTF8.GetString($Body)
        if ($env:TAVERN_GROK_TEST_MODE -eq 'empty-response') { $text = '' }
        $response = @{ choices = @(@{ message = @{ content = $text; reasoning_content = 'private-reasoning' } }) }
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes(($response | ConvertTo-Json -Depth 30 -Compress))
    return @{ RawContentStream = [IO.MemoryStream]::new($bytes) }
}
''' + "\n. '" + script_path + "'\n", encoding="utf-8-sig")
            env = dict(os.environ)
            env.update(TAVERN_GROK_TEST_MODE=mode, TAVERN_GROK_TEST_JOURNAL=str(journal))
            lines = [request if isinstance(request, str) else json.dumps(request, ensure_ascii=False) for request in requests]
            process = subprocess.run(
                [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
                input=("\n".join(lines) + "\n").encode("utf-8"), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=env, timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout = process.stdout.decode("utf-8-sig")
            stderr = process.stderr.decode("utf-8-sig")
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(stderr.strip(), "")
            for private in (SECRET, "credential-private-diagnostic", "network-private-diagnostic", "private-reasoning"):
                self.assertNotIn(private, stdout + stderr)
            responses = [json.loads(line) for line in stdout.splitlines()]
            calls = len(journal.read_text().splitlines()) if journal.exists() else 0
            return responses, calls

    @staticmethod
    def call(arguments, request_id=1, name="ask_grok"):
        return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}}

    def test_initialize_tools_list_ping_and_notifications_are_valid_jsonrpc(self):
        responses, calls = self.run_protocol([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
            {"jsonrpc": "2.0", "id": 4, "method": "initialize", "params": {"protocolVersion": "unsupported"}},
        ])
        self.assertEqual(calls, 0)
        self.assertEqual([item["id"] for item in responses], [1, 2, 3, 4])
        self.assertTrue(all(item["jsonrpc"] == "2.0" for item in responses))
        self.assertEqual(responses[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(responses[3]["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(responses[2]["result"], {})
        tools = {item["name"]: item for item in responses[1]["result"]["tools"]}
        self.assertEqual(set(tools), {"ask_grok", "list_grok_models"})
        self.assertEqual(tools["ask_grok"]["inputSchema"]["required"], ["prompt"])
        self.assertEqual(tools["ask_grok"]["inputSchema"]["properties"]["max_output_tokens"]["maximum"], 32768)

    def test_invalid_prompts_are_rejected_before_credentials_or_network(self):
        arguments = [{}, {"prompt": None}, {"prompt": ""}, {"prompt": " \t "}, {"prompt": 123}, {"prompt": []}, {"prompt": "x" * 200001}]
        responses, calls = self.run_protocol([self.call(args, index) for index, args in enumerate(arguments, 1)], "credential-error")
        self.assertEqual(calls, 0)
        self.assertEqual(len(responses), len(arguments))
        for response in responses:
            self.assertTrue(response["result"]["isError"])
            self.assertIn("prompt must", response["result"]["content"][0]["text"])

    def test_invalid_models_are_rejected_before_credentials_or_network(self):
        models = ["", "gemini-4-argon", "grok-4.7/../models", "grok-4?key=secret", "grok-" + "x" * 124, 123, []]
        responses, calls = self.run_protocol([self.call({"prompt": "hi", "model": model}, index) for index, model in enumerate(models, 1)], "credential-error")
        self.assertEqual(calls, 0)
        for response in responses:
            self.assertTrue(response["result"]["isError"])
            self.assertEqual(response["result"]["content"][0]["text"], "Invalid Grok model ID.")

    def test_token_bounds_and_types_fail_without_network(self):
        tokens = [0, -1, 32769, 1.5, "4096", True, {}, 2 ** 63]
        responses, calls = self.run_protocol([self.call({"prompt": "hi", "max_output_tokens": value}, index) for index, value in enumerate(tokens, 1)], "credential-error")
        self.assertEqual(calls, 0)
        for response in responses:
            self.assertTrue(response["result"]["isError"])
            self.assertIn("max_output_tokens must", response["result"]["content"][0]["text"])

    def test_valid_defaults_and_token_boundaries_forward_unicode_to_local_double(self):
        arguments = [{"prompt": "你好，Grok"}, {"prompt": "minimum", "max_output_tokens": 1}, {"prompt": "maximum", "max_output_tokens": 32768, "model": "grok-test"}]
        responses, calls = self.run_protocol([self.call(args, index) for index, args in enumerate(arguments, 1)])
        self.assertEqual(calls, 3)
        payloads = [json.loads(response["result"]["content"][0]["text"]) for response in responses]
        self.assertEqual([payload["max_tokens"] for payload in payloads], [16384, 1, 32768])
        self.assertEqual(payloads[0]["model"], "grok-4.7")
        self.assertEqual(payloads[0]["messages"], [{"role": "user", "content": "你好，Grok"}])
        self.assertEqual(payloads[2]["model"], "grok-test")
        self.assertFalse(payloads[0]["stream"])
        self.assertNotIn("response_format", payloads[0])

    def test_group_chat_prompt_requests_json_and_model_list_only_returns_ids(self):
        prompt = '<conversation_data>{"messages": []}</conversation_data> 请返回 JSON，包含 "speak"'
        responses, calls = self.run_protocol([self.call({"prompt": prompt}), self.call({}, 2, "list_grok_models")])
        self.assertEqual(calls, 2)
        payload = json.loads(responses[0]["result"]["content"][0]["text"])
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        models = json.loads(responses[1]["result"]["content"][0]["text"])
        self.assertEqual(models, [{"id": "grok-test-one"}, {"id": "grok-test-two"}])

    def test_credential_network_and_empty_response_failures_are_sanitized(self):
        for mode, expected_calls, expected_text in (("credential-error", 0, "connection unavailable"), ("network-error", 1, "connection unavailable"), ("empty-response", 1, "returned no text")):
            with self.subTest(mode=mode):
                responses, calls = self.run_protocol([self.call({"prompt": "hi"})], mode)
                self.assertEqual(calls, expected_calls)
                self.assertTrue(responses[0]["result"]["isError"])
                self.assertIn(expected_text, responses[0]["result"]["content"][0]["text"])

    def test_bad_json_unknown_method_and_unknown_tool_do_not_echo_input(self):
        responses, calls = self.run_protocol([
            '{"id":1,"input":"request-private-diagnostic", broken}',
            {"jsonrpc": "2.0", "id": 2, "method": "unknown-request-private-diagnostic"},
            self.call({}, 3, "unknown-request-private-diagnostic"),
        ])
        self.assertEqual(calls, 0)
        self.assertEqual(responses[0]["error"]["message"], "Invalid MCP request.")
        self.assertEqual(responses[1]["error"]["message"], "Invalid MCP request.")
        self.assertEqual(responses[2]["result"]["content"][0]["text"], "Unknown tool.")
        self.assertNotIn("request-private-diagnostic", json.dumps(responses))


if __name__ == "__main__":
    unittest.main()
