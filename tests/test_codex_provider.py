"""Codex CLI discovery, isolation, protocol, and real process cancellation."""
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from backend import codex_provider as codex


HELP = b"--ignore-user-config --ignore-rules --ephemeral --output-schema --json"
ANSWER = '{"speak":true,"to":"user","content":"你好"}'


def events(text=ANSWER):
    return (json.dumps({"type": "thread.started", "thread_id": "fake"}) + "\n" +
            json.dumps({"type": "item.completed", "item": {"type": "reasoning", "text": "private reasoning"}}) + "\n" +
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": text}}, ensure_ascii=False) + "\n" +
            json.dumps({"type": "turn.completed", "usage": {}}) + "\n").encode("utf-8")


class CodexTests(unittest.TestCase):
    def connection(self, model=None):
        return codex.CodexConnection(sys.executable, True, "configured", model, os.environ)

    def test_missing_cli_is_not_configured(self):
        with patch("backend.codex_provider.shutil.which", return_value=None):
            connection = codex.discover({"PATH": ""})
        self.assertFalse(connection.configured)
        self.assertIn("未找到", connection.detail)

    def test_discovery_requires_chatgpt_login_not_api_key(self):
        for code, login in ((1, b"Not logged in"), (0, b"Logged in using an API key")):
            with self.subTest(login=login), patch("backend.codex_provider._run", side_effect=[(0, HELP, b""), (code, b"", login)]):
                connection = codex.discover({"CODEX_CLI_PATH": sys.executable})
                self.assertFalse(connection.configured)
                self.assertIn("ChatGPT", connection.detail)

    def test_discovery_snapshot_is_immutable_and_status_contains_no_credentials(self):
        source = {"CODEX_CLI_PATH": sys.executable, "PATH": "system-path", "CODEX_HOME": "original-home",
                  "OPENAI_API_KEY": "private-api-key", "CODEX_API_KEY": "private-codex-key",
                  "GEMINI_API_KEY": "private-other-key", "CODEX_THREAD_ID": "parent-chat"}
        with patch("backend.codex_provider._run", side_effect=[(0, HELP, b""), (0, b"", b"Logged in using ChatGPT\n")]):
            connection = codex.discover(source, "gpt-selected")
        source["PATH"] = "changed"
        self.assertTrue(connection.configured)
        self.assertEqual(connection._env["PATH"], "system-path")
        self.assertEqual(connection._env["CODEX_HOME"], "original-home")
        self.assertNotIn("OPENAI_API_KEY", connection._env)
        self.assertNotIn("CODEX_API_KEY", connection._env)
        self.assertNotIn("GEMINI_API_KEY", connection._env)
        self.assertNotIn("CODEX_THREAD_ID", connection._env)
        self.assertNotIn("private", json.dumps(connection.status()))
        self.assertNotIn("original-home", repr(connection))
        with self.assertRaises(FrozenInstanceError):
            connection.configured = False
        with self.assertRaises(TypeError):
            connection._env["PATH"] = "change"

    def test_old_cli_fails_closed_and_unsafe_model_is_not_passed(self):
        with patch("backend.codex_provider._run", return_value=(0, b"old help", b"")):
            connection = codex.discover({"CODEX_CLI_PATH": sys.executable}, '--bad "model"')
        self.assertFalse(connection.configured)
        self.assertIsNone(connection.model)
        self.assertIn("版本", connection.detail)

    def test_success_uses_isolated_cwd_schema_and_no_model_override_by_default(self):
        directories = []

        def run(command, env, cwd, cancel, timeout, input_data=b""):
            directories.append(cwd)
            if command[1:3] == ["login", "status"]:
                return 0, b"", b"Logged in using ChatGPT"
            self.assertEqual(command[:2], [sys.executable, "exec"])
            for flag in ("--json", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check"):
                self.assertIn(flag, command)
            self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
            self.assertNotIn("--model", command)
            self.assertNotIn('forced_login_method="chatgpt"', command)
            self.assertIn('web_search="disabled"', command)
            self.assertIn("features.shell_tool=false", command)
            self.assertIn("features.remote_plugin=false", command)
            self.assertIn("features.unified_exec=false", command)
            self.assertIn('model_reasoning_effort="medium"', command)
            self.assertIn('model_reasoning_summary="none"', command)
            self.assertIn('service_tier="fast"', command)
            self.assertIn('features.fast_mode=true', command)
            schema = Path(command[command.index("--output-schema") + 1])
            self.assertEqual(schema.parent, Path(cwd))
            data = json.loads(schema.read_text(encoding="utf-8"))
            self.assertFalse(data["additionalProperties"])
            self.assertEqual(set(data["required"]), {"speak", "to", "content", "searchQuery"})
            self.assertIn("gpt", data["properties"]["to"]["enum"])
            self.assertIn("grok", data["properties"]["to"]["enum"])
            instructions = next(value for value in command if value.startswith("developer_instructions="))
            self.assertNotIn("You are GPT", instructions)
            self.assertIn("assigned character identity", instructions)
            self.assertEqual(input_data.decode(), "用户问题")
            return 0, events(), b""

        with patch("backend.codex_provider._run", side_effect=run):
            self.assertEqual(self.connection().respond("用户问题", threading.Event()), ANSWER)
        self.assertEqual(len(set(directories)), 1)
        self.assertFalse(Path(directories[0]).exists())

    def test_explicit_selected_model_is_preserved(self):
        with patch("backend.codex_provider._run", side_effect=[(0, b"Logged in using ChatGPT", b""), (0, events(), b"")]) as run:
            self.connection("gpt-selected").respond("question", threading.Event())
        command = run.call_args_list[-1].args[0]
        self.assertEqual(command[command.index("--model") + 1], "gpt-selected")

    def test_deep_reasoning_is_per_request_and_invalid_effort_never_starts(self):
        connection = self.connection("gpt-6.1-sol")
        with patch("backend.codex_provider._run", side_effect=[(0, b"Logged in using ChatGPT", b""), (0, events(), b"")]) as run:
            connection.respond("question", threading.Event(), reasoning_effort="high")
        command = run.call_args_list[-1].args[0]
        self.assertIn('model_reasoning_effort="high"', command)
        self.assertIn('web_search="disabled"', command)
        with patch("backend.codex_provider._run") as run:
            for effort in ("ultra", "none", None, []):
                with self.subTest(effort=effort), self.assertRaises(codex.CodexError):
                    connection.respond("question", threading.Event(), reasoning_effort=effort)
        run.assert_not_called()

    def test_login_switch_to_api_key_does_not_start_exec_or_force_logout(self):
        with patch("backend.codex_provider._run", return_value=(0, b"Logged in using an API key", b"")) as run:
            with self.assertRaisesRegex(codex.CodexError, "ChatGPT 登录"):
                self.connection().respond("question", threading.Event())
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], [sys.executable, "login", "status"])

    def test_status_reads_only_the_snapshot(self):
        with patch("backend.codex_provider._run") as run:
            self.assertTrue(self.connection().status()["configured"])
        run.assert_not_called()

    def test_precancel_never_starts_process(self):
        cancel = threading.Event()
        cancel.set()
        with patch("backend.codex_provider.subprocess.Popen") as start:
            with self.assertRaises(codex.CodexCancelled):
                self.connection().respond("question", cancel)
        start.assert_not_called()

    def test_prompt_and_timeout_validation(self):
        with patch("backend.codex_provider._run") as run:
            for prompt in ("", " ", None, "x" * (codex._MAX_PROMPT + 1)):
                with self.subTest(prompt_type=type(prompt).__name__), self.assertRaises(codex.CodexError):
                    self.connection().respond(prompt, threading.Event())
            for timeout in (0, -1, float("nan"), float("inf")):
                with self.subTest(timeout=timeout), self.assertRaises(codex.CodexError):
                    self.connection().respond("question", threading.Event(), timeout)
        run.assert_not_called()

    def test_malformed_or_incomplete_jsonl_is_rejected(self):
        for output in (b"not json", b"[]", b"\xff", b'{"type":"item.completed","item":{"type":"agent_message","text":4}}',
                       b'{"type":"turn.completed"}', b'{"type":"item.completed","item":{"type":"agent_message","text":"answer"}}'):
            with self.subTest(output=output), self.assertRaises(codex.CodexError):
                codex._extract_response(output)

    def test_failure_details_are_classified_not_returned(self):
        secret = b"private-token 429 quota exceeded"
        with patch("backend.codex_provider._run", side_effect=[(0, b"Logged in using ChatGPT", b""), (1, b"", secret)]):
            with self.assertRaises(codex.CodexError) as caught:
                self.connection().respond("question", threading.Event())
        self.assertIn("额度", str(caught.exception))
        self.assertNotIn("private-token", str(caught.exception))
        with self.assertRaises(codex.CodexError) as caught:
            codex._extract_response(b'{"type":"turn.failed","error":{"message":"secret 401 unauthorized"}}')
        self.assertIn("登录", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))

    def test_process_timeout_terminates_and_reaps(self):
        started = time.monotonic()
        with tempfile.TemporaryDirectory() as cwd:
            with self.assertRaisesRegex(codex.CodexError, "超时"):
                codex._run([sys.executable, "-c", "import time; time.sleep(10)"], os.environ, cwd, threading.Event(), 0.12)
        self.assertLess(time.monotonic() - started, 5)

    def test_cancel_is_responsive_even_if_child_never_reads_large_stdin(self):
        cancel = threading.Event()
        timer = threading.Timer(0.12, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        with tempfile.TemporaryDirectory() as cwd:
            with self.assertRaises(codex.CodexCancelled):
                codex._run([sys.executable, "-c", "import time; time.sleep(10)"], os.environ, cwd, cancel, 5, b"x" * 200000)
        self.assertLess(time.monotonic() - started, 5)

    def test_stdout_and_stderr_are_bounded(self):
        for stream, limit in (("stdout", "_MAX_STDOUT"), ("stderr", "_MAX_STDERR")):
            with self.subTest(stream=stream), tempfile.TemporaryDirectory() as cwd, patch.object(codex, limit, 1024):
                command = [sys.executable, "-c", f"import sys; sys.{stream}.buffer.write(b'x'*100000); sys.{stream}.flush()"]
                with self.assertRaisesRegex(codex.CodexError, "数据过大"):
                    codex._run(command, os.environ, cwd, threading.Event(), 3)

    @unittest.skipUnless(os.name == "nt", "Windows process-tree cleanup")
    def test_windows_job_kills_descendant_after_launcher_has_exited(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as cwd:
            code = ("import subprocess,sys,time; "
                    "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']); "
                    "open('child.pid','w').write(str(child.pid)); time.sleep(0.05)")
            with self.assertRaisesRegex(codex.CodexError, "超时"):
                codex._run([sys.executable, "-c", code], os.environ, cwd, threading.Event(), 0.5)
            pid = int((Path(cwd) / "child.pid").read_text())
            handle = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
            if handle:
                try:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 2000), 0,
                                     "orphaned child outlived cancelled CLI request")
                finally:
                    kernel.CloseHandle(handle)

    def test_process_uses_no_shell_and_round_trips_unicode_stdin(self):
        data = "原样中文输入".encode()
        with tempfile.TemporaryDirectory() as cwd:
            result = codex._run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
                                os.environ, cwd, threading.Event(), 3, data)
        self.assertEqual(result, (0, data, b""))


if __name__ == "__main__":
    unittest.main()
