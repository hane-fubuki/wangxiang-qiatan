"""Lifecycle checks: no tunnel can expose a port the proxy does not own."""
import contextlib
import getpass
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import remote


class RemoteLauncherTests(unittest.TestCase):
    def sandbox(self, directory):
        stack = contextlib.ExitStack()
        work = Path(directory)
        for name, value in {"WORK": work, "STATE": work / "state.json",
                            "PASSWORD": work / "password.txt", "STOP": work / "stop"}.items():
            stack.enter_context(patch.object(remote, name, value))
        stack.enter_context(patch.object(remote, "ensure_binary"))
        stack.enter_context(patch.object(remote, "acquire_lock", return_value=MagicMock()))
        stack.enter_context(patch.object(remote, "health", return_value=True))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        return stack

    def test_occupied_proxy_port_never_starts_tunnel(self):
        with tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
            with patch("backend.remote_access.create_remote_server", side_effect=OSError("port occupied")) as create, \
                    patch.object(remote.subprocess, "Popen") as launch:
                remote.serve()
            launch.assert_not_called()
            self.assertIsNone(create.call_args.args[2])
            self.assertEqual(remote.read_state()["status"], "error")

    def test_proxy_is_bound_before_tunnel_and_existing_app_survives_stop(self):
        with tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
            order = []
            proxy = MagicMock()
            proxy.set_public_host.side_effect = lambda host: order.append(("activate", host))
            process = MagicMock()
            process.pid = 1234
            process.poll.return_value = None

            def create(*args):
                self.assertIsNone(args[2])
                order.append(("bind", args[0]))
                return proxy

            def launch(args, **kwargs):
                order.append(("tunnel", args))
                (remote.WORK / "tunnel.log").write_text("https://fixture-test.trycloudflare.com\n", encoding="utf-8")
                return process

            original_write = remote.write_state

            def write(**values):
                original_write(**values)
                if values.get("status") == "running":
                    remote.STOP.write_text("stop", encoding="utf-8")

            with patch("backend.remote_access.create_remote_server", side_effect=create), \
                    patch.object(remote.subprocess, "Popen", side_effect=launch) as spawn, \
                    patch.object(remote, "write_state", side_effect=write):
                remote.serve()
            self.assertEqual([step[0] for step in order], ["bind", "tunnel", "activate"])
            self.assertEqual(spawn.call_count, 1)
            self.assertIn("http://127.0.0.1:8766", spawn.call_args.args[0])
            process.terminate.assert_called_once()
            proxy.shutdown.assert_called_once()
            proxy.server_close.assert_called_once()
            self.assertEqual(remote.read_state()["status"], "stopped")

    def test_start_detaches_using_the_job_policy(self):
        base_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        cases = [(None, base_flags),
                 (0x2800, base_flags | subprocess.CREATE_BREAKAWAY_FROM_JOB),
                 (0x3000, base_flags)]
        for limits, expected_flags in cases:
            with self.subTest(limits=limits), tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
                with patch.object(remote, "windows_job_limits", return_value=limits), \
                        patch.object(remote.subprocess, "Popen") as spawn:
                    spawn.return_value.pid = 1234
                    remote.spawn_service()
                spawn.assert_called_once()
                self.assertEqual(spawn.call_args.kwargs["creationflags"], expected_flags)
                self.assertEqual(spawn.call_args.args[0][-2:], ["serve", "--independent"])
                self.assertEqual(spawn.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_restricted_job_refuses_to_start_instead_of_inheriting_cleanup(self):
        with tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
            with patch.object(remote, "windows_job_limits", return_value=0x2000), \
                    patch.object(remote.subprocess, "Popen") as spawn:
                with self.assertRaisesRegex(RuntimeError, "不允许后台服务独立运行"):
                    remote.spawn_service()
            spawn.assert_not_called()
            self.assertFalse(remote.STATE.exists())
            self.assertFalse((remote.WORK / "service.log").exists())

    def test_job_inspection_error_prevents_launch(self):
        with tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
            with patch.object(sys, "argv", ["remote.py", "start"]), \
                    patch.object(remote, "is_running", return_value=False), \
                    patch.object(remote, "windows_job_limits", side_effect=RuntimeError("无法检查后台进程启动环境")), \
                    patch.object(remote.subprocess, "Popen") as spawn:
                with self.assertRaisesRegex(SystemExit, "无法检查后台进程启动环境"):
                    remote.main()
            spawn.assert_not_called()

    def test_breakaway_launch_failure_does_not_retry_without_the_flag(self):
        with tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
            error = OSError("launch denied")
            error.winerror = 5
            result_file = remote.WORK / "result.json"
            with patch.object(remote, "windows_job_limits", return_value=0x2800), \
                    patch.object(remote.subprocess, "Popen", side_effect=error) as spawn:
                remote.launch_from_desktop(result_file)
            spawn.assert_called_once()
            self.assertTrue(spawn.call_args.kwargs["creationflags"] & subprocess.CREATE_BREAKAWAY_FROM_JOB)
            self.assertIn("error", json.loads(result_file.read_text(encoding="utf-8")))

    def test_normal_terminal_launches_directly(self):
        with tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
            with patch.object(remote, "windows_job_limits", return_value=None), \
                    patch.object(remote, "spawn_service") as spawn, \
                    patch.object(remote, "launch_with_explorer") as explorer:
                spawn.return_value.pid = 1234
                pid, child = remote.start_background_service()
            self.assertEqual(pid, 1234)
            self.assertIs(child, spawn.return_value)
            explorer.assert_not_called()

    def test_nested_job_starts_through_desktop_and_waits_for_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
            def acknowledge(arguments):
                result_file = next(remote.WORK.glob("launch-*.json"), None)
                self.assertIsNone(result_file)
                self.assertEqual(arguments[0], "-c")
                # The desktop intermediate alone receives the spawn capability.
                with patch.object(remote, "spawn_service") as spawn:
                    spawn.return_value.pid = 2345
                    exec(arguments[1], {})

            with patch.object(remote, "windows_job_limits", return_value=0x2800), \
                    patch.object(remote, "launch_with_explorer", side_effect=acknowledge) as explorer:
                pid, child = remote.start_background_service()
            self.assertEqual(pid, 2345)
            self.assertIsNone(child)
            explorer.assert_called_once()
            self.assertEqual(list(remote.WORK.glob("launch-*.json")), [])

    def test_desktop_error_never_falls_back_to_inherited_job(self):
        with tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
            with patch.object(remote, "windows_job_limits", return_value=0x2800), \
                    patch.object(remote, "launch_with_explorer", side_effect=RuntimeError("desktop unavailable")), \
                    patch.object(remote, "spawn_service") as spawn:
                with self.assertRaisesRegex(RuntimeError, "desktop unavailable"):
                    remote.start_background_service()
            spawn.assert_not_called()

    def test_service_refuses_to_publish_if_an_outer_job_survived(self):
        with tempfile.TemporaryDirectory() as directory, self.sandbox(directory):
            with patch.object(remote, "windows_job_limits", return_value=0x2000), \
                    patch("backend.remote_access.create_remote_server") as create, \
                    patch.object(remote.subprocess, "Popen") as spawn:
                remote.serve(require_independent=True)
            create.assert_not_called()
            spawn.assert_not_called()
            self.assertEqual(remote.read_state()["status"], "error")
            self.assertIn("未能脱离启动环境", remote.read_state()["error"])

    @unittest.skipUnless(os.name == "nt", "Windows process lifecycle")
    def test_real_desktop_child_is_independent_and_survives_launcher_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            result_file = Path(directory) / "result.json"
            child_code = "\n".join([
                "import ctypes,getpass,json,os,remote",
                "from ctypes import wintypes as w",
                "from pathlib import Path",
                "k=ctypes.WinDLL('kernel32',use_last_error=True)",
                "k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; k.OpenProcess.restype=w.HANDLE",
                "k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]; k.WaitForSingleObject.restype=w.DWORD",
                "k.CloseHandle.argtypes=[w.HANDLE]",
                "parent=k.OpenProcess(0x100000,False,os.getppid())",
                "exited=not parent or k.WaitForSingleObject(parent,5000)==0",
                "if parent: k.CloseHandle(parent)",
                f"Path({str(result_file)!r}).write_text(json.dumps({{'job':remote.windows_job_limits(), 'parentExited':exited, 'cwd':os.getcwd(), 'user':getpass.getuser()}}))",
            ])
            intermediate_code = (
                "import remote,subprocess,sys; "
                f"subprocess.Popen([sys.executable,'-c',{child_code!r}],cwd=remote.ROOT,"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,"
                "creationflags=remote.background_creationflags())"
            )
            remote.launch_with_explorer(["-c", intermediate_code])
            deadline = time.monotonic() + 10
            while not result_file.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertTrue(result_file.exists(), "Desktop child did not report its lifecycle")
            result = json.loads(result_file.read_text())
            self.assertIsNone(result["job"])
            self.assertTrue(result["parentExited"])
            self.assertEqual(Path(result["cwd"]), remote.ROOT)
            self.assertEqual(result["user"], getpass.getuser())


if __name__ == "__main__":
    unittest.main()
