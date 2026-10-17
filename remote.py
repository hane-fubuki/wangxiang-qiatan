"""Password-protected HTTPS access via an outbound Cloudflare Quick Tunnel."""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

from backend import APP_NAME
from backend.local_access import APP_PORT

ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".tavern" / "remote"
STATE = WORK / "state.json"
PASSWORD = WORK / "password.txt"
STOP = WORK / "stop"
BINARY = ROOT / ".tavern" / "tools" / "cloudflared.exe"
BINARY_URL = "https://github.com/cloudflare/cloudflared/releases/download/2026.10.0/cloudflared-windows-amd64.exe"
BINARY_SHA256 = "86aee4017b26625cee8484c113558f48effa4cd47f7aa05fcf425604e5d2b23c"
PROXY_PORT = 8766


def read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(**values):
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"pid": os.getpid(), **values}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATE)


def health(port, host=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", "/api/health", headers={"Host": host or f"127.0.0.1:{port}"})
        response = connection.getresponse()
        payload = json.loads(response.read(1024))
        return response.status == 200 and isinstance(payload, dict) and payload.get("ok") is True and (port != APP_PORT or payload.get("app") == APP_NAME)
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def is_running():
    state = read_state()
    return state.get("status") == "running" and health(PROXY_PORT, state.get("host"))


def ensure_binary():
    if os.name != "nt":
        raise RuntimeError("此启动器使用 Windows 版 cloudflared。")
    if BINARY.is_file() and hashlib.sha256(BINARY.read_bytes()).hexdigest() == BINARY_SHA256:
        return
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    temporary = BINARY.with_suffix(".download")
    with urllib.request.urlopen(BINARY_URL, timeout=90) as response, temporary.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    if hashlib.sha256(temporary.read_bytes()).hexdigest() != BINARY_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("cloudflared 下载校验失败，未运行下载文件。")
    temporary.replace(BINARY)


def acquire_lock():
    import msvcrt
    handle = (WORK / "service.lock").open("a+b")
    handle.seek(0)
    if not handle.read(1):
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def windows_job_limits():
    """Return the enclosing Windows job's limits, or None outside a job."""
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                     ctypes.POINTER(wintypes.BOOL)]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                ctypes.c_void_p, wintypes.DWORD,
                                                ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    in_job = wintypes.BOOL()
    if not kernel.IsProcessInJob(kernel.GetCurrentProcess(), None, ctypes.byref(in_job)):
        raise RuntimeError(f"无法检查后台进程启动环境（Windows 错误 {ctypes.get_last_error()}）。")
    if not in_job.value:
        return None
    limits = BasicLimits()
    # JobObjectBasicLimitInformation = 2. Passing NULL queries our own job.
    if not kernel.QueryInformationJobObject(None, 2, ctypes.byref(limits), ctypes.sizeof(limits), None):
        raise RuntimeError(f"无法检查后台进程独立运行权限（Windows 错误 {ctypes.get_last_error()}）。")
    return limits.LimitFlags


def background_creationflags():
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    limits = windows_job_limits()
    if limits is None or limits & 0x1000:  # JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK
        return flags
    if limits & 0x0800:  # JOB_OBJECT_LIMIT_BREAKAWAY_OK
        return flags | subprocess.CREATE_BREAKAWAY_FROM_JOB
    raise RuntimeError("当前启动环境不允许后台服务独立运行。请从普通终端运行 python remote.py start，"
                       "或双击开启外网访问启动器；本次未启动服务。")


def spawn_service():
    flags = background_creationflags()
    with (WORK / "service.log").open("ab") as log:
        return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "serve", "--independent"],
                                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                creationflags=flags)


def launch_with_explorer(arguments):
    """Ask the existing user's desktop to launch a hidden intermediate process."""
    def quote(value):
        return "'" + value.replace("'", "''") + "'"

    script = ("$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; "
              "$shell=New-Object -ComObject Shell.Application; "
              "$desktop=$shell.Windows().FindWindowSW(0,0,8,[ref]0,1); "
              "if ($null -eq $desktop) { throw 'No Explorer desktop available' }; "
              "$desktop.Document.Application.ShellExecute("
              + quote(sys.executable) + "," + quote(subprocess.list2cmdline(arguments)) + ","
              + quote(str(ROOT)) + ",'open',0)")
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        result = subprocess.run([str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
                                 "-EncodedCommand", base64.b64encode(script.encode("utf-16-le")).decode("ascii")],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("无法连接 Windows 桌面启动器。请在已登录的桌面中双击开启外网访问.cmd。") from None
    if result.returncode:
        raise RuntimeError("Windows 桌面启动器未能启动后台服务。请双击开启外网访问.cmd。")


def launch_from_desktop(result_file):
    # Explorer may use its own breakaway-enabled job. Detach once more here;
    # serve --independent checks that no enclosing job survived this launch.
    try:
        child = spawn_service()
        result = {"pid": child.pid}
    except (RuntimeError, OSError) as error:
        result = {"error": str(error)}
    Path(result_file).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


def start_background_service():
    if windows_job_limits() is None:
        child = spawn_service()
        return child.pid, child
    # A tool can have nested jobs: breaking away from its innermost job alone
    # can still inherit an outer KILL_ON_JOB_CLOSE job. Start through Explorer.
    result_file = WORK / f"launch-{secrets.token_hex(12)}.json"
    try:
        code = f"import remote; remote.launch_from_desktop({str(result_file)!r})"
        launch_with_explorer(["-c", code])
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                result = json.loads(result_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                time.sleep(0.1)
                continue
            if result.get("error"):
                raise RuntimeError(result["error"])
            if isinstance(result.get("pid"), int) and result["pid"] > 0:
                return result["pid"], None
            raise RuntimeError("Windows 桌面启动器未返回有效进程信息。")
        raise RuntimeError("Windows 桌面启动器未能及时启动服务，请查看 service.log 或双击开启外网访问.cmd。")
    finally:
        result_file.unlink(missing_ok=True)


def serve(require_independent=False):
    from backend.remote_access import create_remote_server

    WORK.mkdir(parents=True, exist_ok=True)
    lock = acquire_lock()
    if lock is None:
        return
    STOP.unlink(missing_ok=True)
    proxy = tunnel = app_process = None
    proxy_thread = None
    log_handles = []
    failed = False
    hidden = subprocess.CREATE_NO_WINDOW
    try:
        write_state(status="starting")
        if require_independent and windows_job_limits() is not None:
            raise RuntimeError("后台服务未能脱离启动环境，为避免再次意外中断，本次未开启外网入口。"
                               "请从 Windows 桌面双击开启外网访问.cmd。")
        ensure_binary()
        if not PASSWORD.exists():
            PASSWORD.write_text(secrets.token_urlsafe(24) + "\n", encoding="utf-8")
        password = PASSWORD.read_text(encoding="utf-8").strip()
        if len(password) < 16:
            raise RuntimeError("外网访问密码至少需要16个字符，请检查本地密码文件。")
        if not health(APP_PORT):
            app_log = (WORK / "app.log").open("ab")
            log_handles.append(app_log)
            app_process = subprocess.Popen([sys.executable, str(ROOT / "app.py")], cwd=ROOT,
                                           stdin=subprocess.DEVNULL, stdout=app_log, stderr=app_log,
                                           creationflags=hidden)
            for _ in range(40):
                if health(APP_PORT):
                    break
                if app_process.poll() is not None:
                    raise RuntimeError("酒馆本机服务启动失败，请查看 .tavern/remote/app.log。")
                time.sleep(0.25)
            else:
                raise RuntimeError("酒馆本机服务未能就绪。")
        # Own the listener before publishing it. Until the hostname is known the
        # proxy rejects every request; an occupied port never gets a tunnel.
        proxy = create_remote_server(PROXY_PORT, APP_PORT, None, password)
        proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        proxy_thread.start()
        tunnel_path = WORK / "tunnel.log"
        tunnel_log = tunnel_path.open("wb")
        log_handles.append(tunnel_log)
        tunnel = subprocess.Popen([str(BINARY), "tunnel", "--no-autoupdate", "--protocol", "http2",
                                   "--url", f"http://127.0.0.1:{PROXY_PORT}"], cwd=ROOT,
                                  stdin=subprocess.DEVNULL, stdout=tunnel_log, stderr=tunnel_log,
                                  creationflags=hidden)
        deadline = time.monotonic() + 90
        url = None
        while time.monotonic() < deadline and not STOP.exists():
            if tunnel.poll() is not None:
                raise RuntimeError("外网隧道启动失败，请查看 .tavern/remote/tunnel.log。")
            match = re.search(r"https://([a-z0-9-]+\.trycloudflare\.com)", tunnel_path.read_text(encoding="utf-8", errors="replace"))
            if match:
                url, host = match.group(0), match.group(1)
                break
            time.sleep(0.25)
        if not url:
            raise RuntimeError("未能取得外网地址，请检查网络和隧道日志。")
        proxy.set_public_host(host)
        write_state(status="running", url=url, host=host, startedAt=time.time(),
                    tunnelPid=tunnel.pid, passwordFile=str(PASSWORD))
        print(f"外网入口已启动：{url}\n密码保存在：{PASSWORD}", flush=True)
        while not STOP.exists():
            if tunnel.poll() is not None:
                raise RuntimeError("隧道已停止，请重新运行开启外网访问。")
            if app_process is not None and app_process.poll() is not None:
                raise RuntimeError("本机酒馆服务已停止。")
            time.sleep(1)
    except Exception as error:
        failed = True
        # These operational errors contain no password, cookies, or chat data.
        write_state(status="error", error=str(error))
        print(str(error), file=sys.stderr, flush=True)
    finally:
        stop_process(tunnel)
        if proxy is not None:
            proxy.shutdown()
            proxy.server_close()
        if proxy_thread is not None:
            proxy_thread.join(timeout=3)
        stop_process(app_process)
        for handle in log_handles:
            handle.close()
        STOP.unlink(missing_ok=True)
        if not failed:
            write_state(status="stopped")
        lock.close()


def display(state):
    print(f"外网地址：{state['url']}\n密码文件：{PASSWORD}\n电脑与外网入口需要持续运行；重新开启后地址会变化。")


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME}外网入口")
    parser.add_argument("action", choices=("start", "serve", "stop", "status"), nargs="?", default="start")
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--independent", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.action == "serve":
        return serve(require_independent=args.independent)
    if args.action == "stop":
        state = read_state()
        if state.get("status") not in ("starting", "running"):
            print("外网入口未运行。")
            return
        STOP.write_text("stop", encoding="utf-8")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if read_state().get("status") not in ("starting", "running"):
                print("外网入口已关闭。")
                return
            time.sleep(0.25)
        raise SystemExit("关闭尚未完成，请查看 .tavern/remote/service.log。")
    if is_running():
        state = read_state()
        display(state)
        if args.open:
            webbrowser.open(state["url"])
        return
    if args.action == "status":
        state = read_state()
        print(state.get("error") or "外网入口未运行。")
        return
    try:
        child_pid, child = start_background_service()
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    except OSError as error:
        raise SystemExit(f"无法独立启动外网服务（Windows 错误 {error.winerror}）。"
                         "请从普通终端运行 python remote.py start。") from None
    deadline = time.monotonic() + 110
    while time.monotonic() < deadline:
        state = read_state()
        if state.get("pid") == child_pid and state.get("status") == "error":
            raise SystemExit(state.get("error", "启动失败"))
        if is_running():
            display(state)
            if args.open:
                webbrowser.open(state["url"])
            return
        if child is not None and child.poll() is not None:
            raise SystemExit("启动器已退出，请查看 .tavern/remote/service.log。")
        time.sleep(0.5)
    raise SystemExit("入口仍在启动，可稍后运行 python remote.py status 查看。")


if __name__ == "__main__":
    main()
