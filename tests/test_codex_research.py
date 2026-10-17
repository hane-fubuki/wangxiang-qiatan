"""Native web-search evidence, bounded sources, isolation and cancellation."""
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

from backend.codex_provider import CodexConnection, CodexError, CodexCancelled
from backend import codex_research as research


RESULT = {"summary": "官网给出了当前版本 [1]。", "sources": [{"title": "Python", "url": "https://www.python.org/downloads/"}]}


def events(result=None, *, search=True, complete=True):
    rows = [{"type": "thread.started", "thread_id": "fake"}]
    if search:
        rows.append({"type": "item.completed", "item": {"id": "item_1", "type": "web_search", "query": "Python latest official",
                                                        "results": [{"type": "text_result", **RESULT["sources"][0]}]}})
    rows.append({"type": "item.completed", "item": {"type": "reasoning", "text": "never return private reasoning"}})
    rows.append({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(RESULT if result is None else result)}})
    if complete:
        rows.append({"type": "turn.completed"})
    return "\n".join(json.dumps(row) for row in rows).encode()


class ResearchTests(unittest.TestCase):
    def adapter(self, **kwargs):
        return research.CodexResearch(CodexConnection(sys.executable, True, "ok", "gpt-6-astra", os.environ), **kwargs)

    def test_isolated_web_only_live_search_and_structured_provenance(self):
        directories = []
        progress = []

        def run(command, env, cwd, cancel, timeout, input_data=b""):
            directories.append(cwd)
            self.assertNotIn("OPENAI_API_KEY", env)
            if command[1:3] == ["login", "status"]:
                return 0, b"Logged in using ChatGPT", b""
            self.assertEqual(command[command.index("--model") + 1], "gpt-6.1-sol")
            self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
            for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check"):
                self.assertIn(flag, command)
            for config in ('web_search="live"', 'model_reasoning_effort="medium"', 'service_tier="fast"',
                           'features.fast_mode=true', 'model_reasoning_summary="none"', 'features.shell_tool=false',
                           'features.unified_exec=false', 'features.remote_plugin=false', 'features.plugins=false',
                           'features.apps=false', 'features.image_generation=false', 'features.code_mode=false',
                           'features.code_mode_host=true'):
                self.assertIn(config, command)
            schema_path = Path(command[command.index("--output-schema") + 1])
            self.assertEqual(schema_path.parent, Path(cwd))
            self.assertEqual(set(json.loads(schema_path.read_text())["required"]), {"summary", "sources"})
            self.assertEqual(input_data, "现在的 Python".encode())
            return 0, events(), b""

        with patch.object(research, "_run", side_effect=run), patch("backend.codex_provider._run", side_effect=run):
            report = self.adapter().search("现在的 Python", threading.Event(), on_progress=progress.append)
        self.assertEqual(report["summary"], RESULT["summary"])
        self.assertEqual(report["sources"], RESULT["sources"])
        self.assertEqual(report["searchCount"], 1)
        self.assertEqual(report["model"], "gpt-6.1-sol")
        self.assertIn("+00:00", report["checkedAt"])
        self.assertIsInstance(report["elapsedMs"], int)
        self.assertEqual(progress[0]["stage"], "searching")
        self.assertNotIn("private reasoning", json.dumps(report))
        self.assertEqual(len(set(directories)), 1)
        self.assertFalse(Path(directories[0]).exists())

    def test_deep_only_changes_per_request_effort(self):
        with patch.object(research, "_logged_in", return_value=True), patch.object(research, "_run", return_value=(0, events(), b"")) as run:
            result = self.adapter().search("查证", threading.Event(), deep=True)
        self.assertIn('model_reasoning_effort="high"', run.call_args.args[0])
        self.assertEqual(result["reasoningEffort"], "high")

    def test_status_is_safe_and_read_only(self):
        with patch.object(research, "_run") as run:
            status = self.adapter().status()
        run.assert_not_called()
        self.assertTrue(status["configured"])
        self.assertEqual(status["mode"], "live")
        self.assertNotIn(sys.executable, json.dumps(status))

    def test_precancel_and_invalid_inputs_never_start(self):
        adapter = self.adapter()
        cancel = threading.Event()
        cancel.set()
        with patch.object(research, "_logged_in") as login:
            with self.assertRaises(CodexCancelled):
                adapter.search("hi", cancel)
            for value in ("", " ", None, "x" * (research.MAX_PROMPT_BYTES + 1)):
                with self.assertRaises(CodexError):
                    adapter.search(value, threading.Event())
        login.assert_not_called()
        for timeout in (True, 0, -1, 301, float("nan"), float("inf")):
            with self.assertRaises(CodexError):
                self.adapter(timeout=timeout)

    def test_cancel_after_transport_is_not_returned_as_result(self):
        cancel = threading.Event()
        def run(*args):
            cancel.set()
            return 0, events(), b""
        with patch.object(research, "_logged_in", return_value=True), patch.object(research, "_run", side_effect=run):
            with self.assertRaises(CodexCancelled):
                self.adapter().search("hi", cancel)

    def test_login_failure_safe_transport_errors_and_timeout_propagate(self):
        with patch.object(research, "_logged_in", return_value=False), patch.object(research, "_run") as run:
            with self.assertRaisesRegex(CodexError, "ChatGPT 登录"):
                self.adapter().search("hi", threading.Event())
        run.assert_not_called()
        with patch.object(research, "_logged_in", return_value=True), patch.object(research, "_run", return_value=(1, b"secret-token", b"429 quota")):
            with self.assertRaisesRegex(CodexError, "额度") as caught:
                self.adapter().search("hi", threading.Event())
        self.assertNotIn("secret", str(caught.exception))
        with patch.object(research, "_logged_in", return_value=True), patch.object(research, "_run", side_effect=CodexError("响应超时")):
            with self.assertRaisesRegex(CodexError, "超时"):
                self.adapter().search("hi", threading.Event())

    def test_claims_of_browsing_cannot_replace_completed_tool_event(self):
        with self.assertRaisesRegex(CodexError, "实际联网"):
            research._report(events(search=False))
        for item in ({"type": "web_search", "query": "test", "status": "failed"},
                     {"type": "web_search", "query": "test", "error": "bad"},
                     {"type": "web_search", "query": "test", "status": "in_progress"},
                     {"type": "web_search"}):
            with self.subTest(item=item):
                output = json.dumps({"type": "item.completed", "item": item}).encode() + b"\n" + events(search=False)
                with self.assertRaises(CodexError):
                    research._report(output)
        started = json.dumps({"type": "item.started", "item": {"type": "web_search", "query": "test"}}).encode()
        with self.assertRaises(CodexError):
            research._report(started + b"\n" + events(search=False))
        with self.assertRaises(CodexError):
            research._report(events(complete=False))

    def test_sources_and_summary_are_bounded_and_validated_together(self):
        for result in ([], {"summary": "", "sources": RESULT["sources"]},
                       {"summary": "x" * 6001, "sources": RESULT["sources"]},
                       {"summary": "ok", "sources": []},
                       {"summary": "ok", "sources": RESULT["sources"] * 9},
                       {"summary": "ok", "sources": [{"title": "Private", "url": "http://localhost/secret"}]},
                       {"summary": "ok", "sources": [{"title": " ", "url": "https://www.python.org/"}]}):
            with self.subTest(result=str(result)[:50]), self.assertRaises(CodexError):
                research._report(events(result))

    def test_source_urls_and_titles_must_come_from_actual_tool_results(self):
        invented = {"summary": "ok [1]", "sources": [{"title": "Invented", "url": "https://www.python.org/nonexistent-release/"}]}
        with self.assertRaisesRegex(CodexError, "公开来源"):
            research._report(events(invented))
        renamed = {"summary": "ok [1]", "sources": [{"title": "Model invented title", "url": RESULT["sources"][0]["url"]}]}
        self.assertEqual(research._report(events(renamed))["sources"][0]["title"], "Python")
        rows = [json.loads(line) for line in events().decode().splitlines()]
        rows[1]["item"].pop("results")
        with self.assertRaisesRegex(CodexError, "公开来源"):
            research._report("\n".join(json.dumps(row) for row in rows).encode())

    def test_only_public_http_sources_are_allowed(self):
        unsafe = (None, "javascript:alert(1)", "file:///secret", "https://user:pass@example.com/", "http://localhost/",
                  "http://127.0.0.1/", "http://10.0.0.1/", "http://172.16.0.1/", "http://192.168.2.2/",
                  "http://[::1]/", "http://169.254.169.254/", "http://[fc00::1]/", "http://2130706433/",
                  "http://0x7f000001/", "http://127.1/", "http://0x7f.0.0.1/", "http://service.internal/",
                  "http://device.local/", "http://example.com:8765/", "https://good.com\\@evil.com/",
                  "https://example.com/a\nb", "https://example.com/%0D%0A", "https://example.com:bad/",
                  "https://localhost./", "https://bad..com/")
        for url in unsafe:
            with self.subTest(url=url):
                self.assertIsNone(research.public_url(url))
        for url in ("https://www.python.org/downloads/", "http://example.com/page?q=one#two", "https://8.8.8.8/"):
            self.assertEqual(research.public_url(url), url)


if __name__ == "__main__":
    unittest.main()
