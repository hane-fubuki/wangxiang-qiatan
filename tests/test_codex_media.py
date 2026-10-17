"""Native media isolation and provenance; no real model calls in tests."""
import json
from io import BytesIO
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zlib

from PIL import Image

from backend import codex_media as media
from backend.codex_provider import CodexConnection, CodexError, CodexCancelled, _run


THREAD = "12345678-abcd-1234-abcd-123456789abc"


def png(color=b"\0\x80\xff"):
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0" + color)) + chunk(b"IEND", b""))


def events(thread=THREAD, text="图片中是一个蓝色图形。", complete=True):
    items = [{"type": "thread.started", "thread_id": thread},
             {"type": "item.completed", "item": {"type": "agent_message", "text": text}}]
    if complete:
        items.append({"type": "turn.completed", "usage": {}})
    return ("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n").encode()


def report(description="图片中是一个蓝色图形。", needs=False, reason="none", detail="", refused=False):
    return events(text=json.dumps({"description": description, "needs_deep_review": needs,
                                   "reason": reason, "unresolved_detail": detail, "refused": refused}, ensure_ascii=False))


class CodexMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.codex_home = self.root / "codex"
        self.generated = self.codex_home / "generated_images"
        self.output = self.root / "output"
        self.source = self.root / "reference.png"
        self.source.write_bytes(png())
        env = {**os.environ, "CODEX_HOME": str(self.codex_home), "OPENAI_API_KEY": "secret-key"}
        self.connection = CodexConnection(sys.executable, True, "configured", "gpt-selected", env)
        self.adapter = media.CodexMedia(self.connection, self.output)
        self.cancel = threading.Event()

    def produce(self, name="exec-produced.png", data=None):
        directory = self.generated / THREAD
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_bytes(png() if data is None else data)
        return path

    def run_fake(self, function):
        return patch("backend.codex_media._run", side_effect=function)

    def test_status_is_cached_and_contains_no_credentials_or_paths(self):
        with patch("backend.codex_media._run") as run, patch("backend.codex_media._logged_in") as login:
            status = self.adapter.status()
        self.assertTrue(status["configured"])
        self.assertEqual(status["source"], "codex")
        self.assertEqual(status["generationSpeed"], {"serviceTier": "fast", "reasoningEffort": "low"})
        self.assertNotIn("secret-key", json.dumps(status))
        self.assertNotIn(str(self.root), json.dumps(status))
        run.assert_not_called()
        login.assert_not_called()

    def test_analyze_attaches_isolated_copies_with_all_tools_disabled(self):
        directories = []

        def run(command, env, cwd, cancel, timeout, input_data):
            directories.append(cwd)
            attached = Path(command[command.index("--image") + 1])
            self.assertEqual(attached.parent, Path(cwd))
            self.assertEqual(attached.read_bytes(), png())
            self.assertNotEqual(attached, self.source)
            for flag in ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--json"):
                self.assertIn(flag, command)
            for disabled in ("shell_tool", "unified_exec", "remote_plugin", "plugins", "image_generation", "code_mode_host", "view_image"):
                self.assertIn(f"features.{disabled}=false", command)
            self.assertIn('web_search="disabled"', command)
            self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
            self.assertEqual(command[command.index("--model") + 1], "gpt-6.1-sol")
            self.assertIn('service_tier="fast"', command)
            self.assertIn('model_reasoning_effort="medium"', command)
            self.assertIn("features.fast_mode=true", command)
            schema = json.loads(Path(command[command.index("--output-schema") + 1]).read_text())
            self.assertIn("needs_deep_review", schema["required"])
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertEqual(input_data.decode(), "请描述图片")
            self.assertLessEqual(timeout, 180)
            return 0, events(), b""

        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run):
            self.assertEqual(self.adapter.analyze([self.source], "请描述图片", self.cancel), "图片中是一个蓝色图形。")
        self.assertTrue(directories)
        self.assertTrue(all(not Path(path).exists() for path in directories))

    def test_visual_difficulty_escalates_once_and_checks_login_once(self):
        calls, progress = [], []

        def run(command, env, cwd, cancel, timeout, input_data):
            calls.append(command[command.index("--model") + 1])
            self.assertEqual(Path(command[command.index("--image") + 1]).read_bytes(), png())
            if len(calls) == 1:
                self.assertIn('model_reasoning_effort="medium"', command)
                return 0, report("蓝色图形右侧的数字尚未确认。", True, "small_text", "右侧标签的第二位数字"), b""
            self.assertIn('model_reasoning_effort="ultra"', command)
            self.assertIn('service_tier="fast"', command)
            self.assertIn("第二位数字", input_data.decode())
            return 0, report("右侧标签为 12。", True, "small_text", "继续检查"), b""

        with patch("backend.codex_media._logged_in", return_value=True) as login, self.run_fake(run):
            result = self.adapter.analyze_report([self.source], "读出右侧数字", self.cancel, on_progress=progress.append)
        self.assertEqual(calls, ["gpt-6.1-sol", "gpt-6-astra"])
        self.assertEqual(login.call_count, 1)
        self.assertEqual([item["stage"] for item in progress], ["fast", "deep"])
        self.assertEqual(result["model"], "gpt-6-astra")
        self.assertEqual(result["reasoningEffort"], "ultra")
        self.assertEqual(result["description"], "右侧标签为 12。")
        self.assertTrue(result["escalated"])
        self.assertFalse(result["cached"])
        self.assertEqual(self.connection.model, "gpt-selected")

    def test_explicit_deep_mode_skips_fast_pass(self):
        calls = []

        def run(command, env, cwd, cancel, timeout, input_data):
            calls.append(command[command.index("--model") + 1])
            self.assertIn('model_reasoning_effort="ultra"', command)
            self.assertIn('service_tier="fast"', command)
            self.assertLessEqual(timeout, 420)
            return 0, report("图中左侧物体位于右侧物体前方。"), b""

        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run):
            result = self.adapter.analyze_report([self.source], "深入检查空间关系", self.cancel, mode="deep")
        self.assertEqual(calls, ["gpt-6-astra"])
        self.assertFalse(result["escalated"])

    def test_no_visual_evidence_and_refusals_never_escalate(self):
        outputs = [
            events(text="无法协助这一请求。"),
            report("图形是蓝色。", True, "fine_detail", ""),
            report("图形是蓝色。", True, "none", "问题很长"),
            report("无法协助这一请求。", True, "fine_detail", "细节", True),
            report("I cannot assist with that request.", True, "fine_detail", "细节", False),
            report("该细节不在画面内。"),
            report("蓝色图形。", True, ["small_text"], "细节"),
        ]
        for index, output in enumerate(outputs):
            with self.subTest(index=index), patch("backend.codex_media._logged_in", return_value=True), \
                    self.run_fake(lambda *args: (0, output, b"")) as run:
                result = self.adapter.analyze_report([self.source], f"观察 {index}", self.cancel)
            self.assertEqual(run.call_count, 1)
            self.assertFalse(result["escalated"])
            self.assertEqual(result["model"], "gpt-6.1-sol")

    def test_deep_pass_adds_lossless_tiles_while_fast_pass_retains_only_original(self):
        with Image.new("RGB", (4000, 2400), "white") as source, BytesIO() as target:
            source.save(target, format="PNG")
            large = target.getvalue()
        self.source.write_bytes(large)
        calls = []

        def run(command, env, cwd, cancel, timeout, input_data):
            paths = [Path(command[index + 1]) for index, value in enumerate(command) if value == "--image"]
            calls.append(len(paths))
            self.assertEqual(paths[0].read_bytes(), large)
            if len(calls) == 1:
                self.assertEqual(len(paths), 1)
                return 0, report("细字尚未确认。", True, "small_text", "图中标签"), b""
            self.assertEqual(len(paths), 5)
            for path in paths[1:]:
                with Image.open(path) as crop:
                    self.assertLessEqual(max(crop.size), 2048)
            self.assertIn('"sourceImage": 1', input_data.decode())
            self.assertIn("未放大", input_data.decode())
            return 0, report("标签为 42。"), b""

        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run):
            result = self.adapter.analyze_report([self.source], "读取图中标签", self.cancel)
        self.assertEqual(calls, [1, 5])
        self.assertEqual(result["cropCount"], 4)
        self.assertEqual(result["model"], "gpt-6-astra")

    def test_exact_content_question_mode_cache_and_expiry(self):
        duplicate = self.root / "same-image.png"
        duplicate.write_bytes(png())
        alternative = self.root / "other-image.png"
        alternative.write_bytes(png(b"\xff\0\0"))
        progress = []
        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(lambda *args: (0, report(), b"")) as run:
            first = self.adapter.analyze_report([self.source], "颜色是什么", self.cancel)
            second = self.adapter.analyze_report([duplicate], "颜色是什么", self.cancel, on_progress=progress.append)
            self.assertFalse(first["cached"])
            self.assertTrue(second["cached"])
            self.assertEqual(progress[0]["stage"], "cached")
            self.assertEqual(run.call_count, 1)
            # Returned dictionaries cannot mutate the cached report.
            second["description"] = "changed"
            third = self.adapter.analyze_report([self.source], "颜色是什么", self.cancel)
            self.assertNotEqual(third["description"], "changed")
            self.adapter.analyze_report([self.source], "位置是什么", self.cancel)
            self.adapter.analyze_report([alternative], "颜色是什么", self.cancel)
            self.adapter.analyze_report([self.source], "颜色是什么", self.cancel, mode="deep")
            self.assertEqual(run.call_count, 4)
            with patch.object(media, "ANALYSIS_CACHE_TTL", 0):
                fourth = self.adapter.analyze_report([self.source], "颜色是什么", self.cancel)
            self.assertFalse(fourth["cached"])
            self.assertEqual(run.call_count, 5)

    def test_lru_cache_is_bounded_and_eviction_is_by_recent_use(self):
        with patch("backend.codex_media._logged_in", return_value=True), \
                self.run_fake(lambda *args: (0, report(), b"")) as run, patch.object(media, "ANALYSIS_CACHE_SIZE", 2):
            for question in ("first", "second", "first", "third", "first", "second"):
                self.adapter.analyze_report([self.source], question, self.cancel)
            self.assertEqual(run.call_count, 4)
            self.assertEqual(len(self.adapter._analysis_cache), 2)

    def test_deep_failure_returns_marked_sol_result_without_caching(self):
        first = report("初步识别为数字 1，第二位不确定。", True, "small_text", "第二位数字")
        outputs = iter([(0, first, b""), (1, b"", b"private failure"), (0, first, b""), (1, b"", b"private failure")])
        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(lambda *args: next(outputs)) as run:
            result = self.adapter.analyze_report([self.source], "读出数字", self.cancel)
            again = self.adapter.analyze_report([self.source], "读出数字", self.cancel)
        self.assertEqual(run.call_count, 4)
        self.assertEqual(result["model"], "gpt-6.1-sol")
        self.assertEqual(result["reasoningEffort"], "medium")
        self.assertTrue(result["escalated"])
        self.assertIn("未完成", result["warning"])
        self.assertNotIn("private", json.dumps(result))
        self.assertFalse(again["cached"])
        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(lambda *args: (1, b"", b"private failure")):
            with self.assertRaises(CodexError):
                self.adapter.analyze_report([self.source], "读出数字", self.cancel, mode="deep")

    def test_cancelled_results_are_not_cached_and_precancel_bypasses_cache(self):
        def cancelled(*args):
            self.cancel.set()
            return 0, report(), b""

        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(cancelled):
            with self.assertRaises(CodexCancelled):
                self.adapter.analyze_report([self.source], "描述", self.cancel)
        self.assertFalse(self.adapter._analysis_cache)
        self.cancel.clear()
        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(lambda *args: (0, report(), b"")) as run:
            self.adapter.analyze_report([self.source], "描述", self.cancel)
            self.cancel.set()
            with self.assertRaises(CodexCancelled):
                self.adapter.analyze_report([self.source], "描述", self.cancel)
            self.assertEqual(run.call_count, 1)

    def test_cancel_during_deep_pass_does_not_return_partial_or_cache(self):
        calls = []

        def run(*args):
            calls.append(True)
            if len(calls) == 2:
                self.cancel.set()
            return 0, report("数字尚不清晰。", True, "small_text", "第二位数字"), b""

        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run):
            with self.assertRaises(CodexCancelled):
                self.adapter.analyze_report([self.source], "读出数字", self.cancel)
        self.assertFalse(self.adapter._analysis_cache)

    def test_invalid_report_is_not_cached(self):
        for output in (events(text="{}"), events(text='{"description":3}'), events(text='{"description":')):
            with self.subTest(output=output), patch("backend.codex_media._logged_in", return_value=True), \
                    self.run_fake(lambda *args: (0, output, b"")):
                with self.assertRaises(CodexError):
                    self.adapter.analyze_report([self.source], "描述", self.cancel)
            self.assertFalse(self.adapter._analysis_cache)

    def test_generate_accepts_only_new_thread_directory_and_persists_copy(self):
        def run(command, env, cwd, cancel, timeout, input_data):
            self.assertIn("features.image_generation=true", command)
            self.assertIn("features.code_mode_host=true", command)
            self.assertIn("features.shell_tool=false", command)
            self.assertIn("features.remote_plugin=false", command)
            self.assertIn("features.plugins=false", command)
            self.assertIn('web_search="disabled"', command)
            self.assertIn("features.fast_mode=true", command)
            self.assertIn('service_tier="fast"', command)
            self.assertIn('model_reasoning_effort="low"', command)
            self.assertIn('model_reasoning_summary="none"', command)
            self.assertIn('model_verbosity="low"', command)
            self.assertEqual(command[command.index("--model") + 1], "gpt-selected")
            instructions = next(value for value in command if value.startswith("developer_instructions="))
            self.assertIn("one native image-generation call", instructions)
            self.assertIn("Return immediately after success", instructions)
            self.assertIn("supplied references", instructions)
            self.assertIn("character visual skills", instructions)
            self.assertIn("latest explicit user request overrides", instructions)
            self.assertLessEqual(timeout, 600)
            self.assertEqual(Path(command[command.index("--image") + 1]).read_bytes(), png())
            self.produce()
            # No tool-output event/path is emitted by the verified CLI version.
            return 0, events(text="完成。"), b""

        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run):
            output = self.adapter.generate("按参考图画一张新图", [self.source], self.cancel)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0].parent, self.output)
        self.assertEqual(output[0].read_bytes(), png())
        self.assertNotEqual(output[0].name, "exec-produced.png")

    def test_model_text_paths_and_other_thread_outputs_are_never_used(self):
        unrelated = self.generated / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        unrelated.mkdir(parents=True)
        outside = unrelated / "existing.png"
        outside.write_bytes(png())
        response = events(text=f"![图片]({outside})")
        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(lambda *args: (0, response, b"")):
            with self.assertRaisesRegex(CodexError, "没有产生"):
                self.adapter.generate("draw", [], self.cancel)
        self.assertFalse(self.output.exists())

    def test_reused_thread_directory_is_rejected_even_if_image_is_valid(self):
        self.produce()
        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(lambda *args: (0, events(), b"")):
            with self.assertRaisesRegex(CodexError, "没有产生"):
                self.adapter.generate("draw", [], self.cancel)
        self.assertFalse(self.output.exists())

    def test_invalid_or_oversized_artifact_rolls_back_partial_batch(self):
        for invalid in (b"<svg>not a native raster image</svg>", b"x" * 101):
            with self.subTest(kind=invalid[:8]):
                if self.generated.exists():
                    for path in (self.generated / THREAD).iterdir():
                        path.unlink()
                    (self.generated / THREAD).rmdir()

                def run(*args):
                    self.produce("a-valid.png")
                    self.produce("b-invalid.png", invalid)
                    return 0, events(), b""

                with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run), patch.object(media, "MAX_IMAGE_BYTES", 100):
                    with self.assertRaises(CodexError):
                        self.adapter.generate("draw", [], self.cancel)
                self.assertFalse(self.output.exists() and list(self.output.iterdir()))

    def test_linked_thread_directory_is_rejected(self):
        def run(*args):
            self.produce()
            return 0, events(), b""
        original = media._is_link
        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run), \
                patch("backend.codex_media._is_link", side_effect=lambda path: path.name == THREAD or original(path)):
            with self.assertRaises(CodexError):
                self.adapter.generate("draw", [], self.cancel)
        self.assertFalse(self.output.exists())

    def test_validation_and_precancel_start_no_process(self):
        with patch("backend.codex_media._run") as run, patch("backend.codex_media._logged_in") as login:
            for paths, prompt in (([], "describe"), ([self.source] * 5, "describe"), ([self.source], ""),
                                  ([self.source], "\ud800"), ([self.source], "x" * (media.MAX_PROMPT_BYTES + 1)),
                                  ([self.root / "missing.png"], "describe")):
                with self.subTest(prompt_length=len(prompt)), self.assertRaises(CodexError):
                    self.adapter.analyze(paths, prompt, self.cancel)
            self.cancel.set()
            with self.assertRaises(CodexCancelled):
                self.adapter.generate("draw", [], self.cancel)
        run.assert_not_called()
        login.assert_not_called()

    def test_login_switch_prevents_media_exec(self):
        with patch("backend.codex_media._logged_in", return_value=False), patch("backend.codex_media._run") as run:
            with self.assertRaisesRegex(CodexError, "ChatGPT 登录"):
                self.adapter.analyze([self.source], "describe", self.cancel)
        run.assert_not_called()

    def test_response_errors_are_safe_and_incomplete_events_fail_closed(self):
        for output in (b"not-json", b"[]", b"\xff", events(thread="../../auth.json"), events(complete=False),
                       events() + events(), b"x" * (media.MAX_EVENTS_BYTES + 1)):
            with self.subTest(output=output[:20]), self.assertRaises(CodexError):
                media._completed_thread(output)
        error = b'{"type":"turn.failed","error":{"message":"secret-token 401 unauthorized"}}'
        with self.assertRaises(CodexError) as caught:
            media._completed_thread(error)
        self.assertIn("登录", str(caught.exception))
        self.assertNotIn("secret-token", str(caught.exception))
        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(lambda *args: (1, b"", b"secret-token 429 quota")):
            with self.assertRaises(CodexError) as caught:
                self.adapter.generate("draw", [], self.cancel)
        self.assertIn("额度", str(caught.exception))
        self.assertNotIn("secret-token", str(caught.exception))

    def test_cancel_after_generation_does_not_publish_artifact(self):
        def run(*args):
            self.produce()
            self.cancel.set()
            return 0, events(), b""
        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run):
            with self.assertRaises(CodexCancelled):
                self.adapter.generate("draw", [], self.cancel)
        self.assertFalse(self.output.exists())

    def test_cancel_during_copy_removes_partial_output(self):
        original_read = media._read_image

        def read(path):
            result = original_read(path)
            self.cancel.set()
            return result

        def run(*args):
            self.produce()
            return 0, events(), b""

        with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run), patch("backend.codex_media._read_image", side_effect=read):
            with self.assertRaises(CodexCancelled):
                self.adapter.generate("draw", [], self.cancel)
        self.assertFalse(self.output.exists() and list(self.output.iterdir()))

    def test_process_timeout_and_cancellation_propagate_and_cleanup_temp_cwd(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                token = threading.Event()
                directories = []
                adapter = media.CodexMedia(self.connection, self.output, analyze_timeout=3 if cancelled else .15)

                def run(command, env, cwd, cancel, timeout, input_data):
                    directories.append(cwd)
                    return _run([sys.executable, "-c", "import time; time.sleep(10)"], env, cwd, cancel, timeout)

                timer = threading.Timer(.15, token.set) if cancelled else None
                if timer:
                    timer.start()
                started = time.monotonic()
                try:
                    with patch("backend.codex_media._logged_in", return_value=True), self.run_fake(run):
                        with self.assertRaises(CodexCancelled if cancelled else CodexError):
                            adapter.analyze([self.source], "describe", token)
                finally:
                    if timer:
                        timer.cancel()
                self.assertLess(time.monotonic() - started, 5)
                self.assertTrue(directories)
                self.assertTrue(all(not Path(path).exists() for path in directories))

    def test_timeout_settings_are_bounded(self):
        for value in (0, -1, 601, float("inf"), float("nan"), True, "600"):
            with self.subTest(value=value), self.assertRaises(CodexError):
                media.CodexMedia(self.connection, self.output, timeout=value)


if __name__ == "__main__":
    unittest.main()
