"""Run all three real bridge sources against credential/network test doubles.

No local credential or API is accessed. The doubles echo only the outbound
body as a final answer; hidden thought fields must never leave the bridge.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(POWERSHELL, "PowerShell is not installed")
class ReasoningMcpTests(unittest.TestCase):
    def protocol(self, provider, arguments, mode="success"):
        bridge = ROOT / "integrations" / provider / (provider + "-mcp.ps1")
        with tempfile.TemporaryDirectory() as directory:
            wrapper = Path(directory) / "bridge-fixture.ps1"
            wrapper.write_text(r'''
function Import-Clixml {
    param($LiteralPath)
    $stub = [pscustomobject]@{}
    $stub | Add-Member -MemberType ScriptMethod -Name GetNetworkCredential -Value { return [pscustomobject]@{ Password = 'local-test-secret' } }
    return $stub
}
function Mock-Response($Body) {
    $text = [Text.Encoding]::UTF8.GetString($Body)
    $empty = $env:TAVERN_REASONING_TEST_MODE -eq 'empty'
    $limited = $env:TAVERN_REASONING_TEST_MODE -eq 'limited'
    if ($empty -or $limited) { $text = '' }
    return @{
        choices = @(@{ message = @{ content = $text; reasoning_content = 'private-hidden-thoughts' }; finish_reason = $(if ($limited) { 'length' } else { 'stop' }) })
        candidates = @(@{ content = @{ parts = @(@{ thought = $true; text = 'private-hidden-thoughts' }, @{ text = $text }) }; finishReason = $(if ($limited) { 'MAX_TOKENS' } else { 'STOP' }) })
    }
}
function Invoke-RestMethod {
    param($Uri, $Headers, $TimeoutSec, $Method, $ContentType, $Body)
    if ($TimeoutSec -ne 300) { throw 'unexpected timeout' }
    return Mock-Response $Body
}
function Invoke-WebRequest {
    param($Uri, $Headers, $TimeoutSec, $MaximumRedirection, $Method, $ContentType, $Body, [switch]$UseBasicParsing)
    if ($TimeoutSec -ne 300) { throw 'unexpected timeout' }
    $bytes = [Text.Encoding]::UTF8.GetBytes(((Mock-Response $Body) | ConvertTo-Json -Depth 30 -Compress))
    return @{ RawContentStream = [IO.MemoryStream]::new($bytes) }
}
''' + "\n. '" + str(bridge).replace("'", "''") + "'\n", encoding="utf-8-sig")
            requests = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}]
            requests += [{"jsonrpc": "2.0", "id": index, "method": "tools/call", "params": {"name": "ask_" + provider, "arguments": args}}
                         for index, args in enumerate(arguments, 2)]
            env = dict(os.environ, TAVERN_REASONING_TEST_MODE=mode)
            result = subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
                                    input=("\n".join(json.dumps(item, ensure_ascii=False) for item in requests) + "\n").encode("utf-8"),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=20,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8-sig"))
            self.assertEqual(result.stderr.strip(), b"")
            text = result.stdout.decode("utf-8-sig")
            self.assertNotIn("private-hidden-thoughts", text)
            self.assertNotIn("local-test-secret", text)
            return [json.loads(line)["result"] for line in text.splitlines()]

    def test_real_bridges_expose_levels_use_native_parameters_and_keep_json_format(self):
        models = {"deepseek": "deepseek-v4-pro", "gemini": "gemini-4-argon", "grok": "grok-4.7"}
        prompt = '<conversation_data>中文：请返回 JSON "speak"，含可选 searchQuery</conversation_data>'
        for provider, model in models.items():
            with self.subTest(provider=provider):
                replies = self.protocol(provider, [{"prompt": prompt, "model": model},
                                                   {"prompt": prompt, "model": model, "reasoning_effort": "high"},
                                                   {"prompt": "custom", "model": provider + "-custom", "reasoning_effort": "high"}])
                schema = next(tool["inputSchema"] for tool in replies[0]["tools"] if tool["name"] == "ask_" + provider)
                self.assertEqual(schema["properties"]["reasoning_effort"]["enum"], ["medium", "high"])
                payloads = [json.loads(reply["content"][0]["text"]) for reply in replies[1:]]
                for effort, payload, budget in zip(("medium", "high"), payloads[:2], (16384, 32768)):
                    if provider == "gemini":
                        config = payload["generationConfig"]
                        self.assertEqual(config["thinkingConfig"], {"thinkingLevel": effort, "includeThoughts": False})
                        self.assertEqual(config["maxOutputTokens"], budget)
                        self.assertEqual(config["responseMimeType"], "application/json")
                        self.assertIn(prompt, payload["contents"][0]["parts"][0]["text"])
                    else:
                        self.assertEqual(payload["max_tokens"], budget)
                        self.assertEqual(payload["reasoning_effort"], "high" if provider == "deepseek" else effort)
                        self.assertEqual(payload["response_format"], {"type": "json_object"})
                        self.assertIn(prompt, payload["messages"][0]["content"])
                        if provider == "deepseek":
                            self.assertEqual(payload["thinking"], {"type": "enabled"})
                custom = payloads[2]
                self.assertNotIn("thinking", custom)
                self.assertNotIn("reasoning_effort", custom)
                self.assertNotIn("thinkingConfig", custom.get("generationConfig", {}))

    def test_invalid_levels_and_token_types_are_rejected(self):
        for provider in ("deepseek", "gemini", "grok"):
            with self.subTest(provider=provider):
                arguments = [{"prompt": "hi", "reasoning_effort": effort} for effort in ("ultra", "none", "HIGH", "", [], True)]
                arguments += [{"prompt": "hi", "max_output_tokens": token} for token in (1.5, "4096", True, 0, 32769)]
                replies = self.protocol(provider, arguments)
                self.assertTrue(all(reply.get("isError") for reply in replies[1:]))

    def test_no_final_text_and_budget_exhaustion_do_not_return_raw_response_or_thoughts(self):
        for provider in ("deepseek", "gemini", "grok"):
            for mode in ("empty", "limited"):
                with self.subTest(provider=provider, mode=mode):
                    replies = self.protocol(provider, [{"prompt": "hi"}], mode=mode)
                    self.assertTrue(replies[1]["isError"])
                    text = replies[1]["content"][0]["text"]
                    self.assertNotIn("choices", text)
                    self.assertNotIn("candidates", text)
                    if mode == "limited":
                        self.assertIn("token limit", text)


if __name__ == "__main__":
    unittest.main()
