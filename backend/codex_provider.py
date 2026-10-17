"""ChatGPT-authenticated Codex CLI transport, without reading credential files."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from types import MappingProxyType
from typing import Mapping


class CodexError(RuntimeError):
    """A diagnostic safe to display in a chat; never contains raw CLI output."""


class CodexCancelled(CodexError):
    pass


_MAX_STDOUT = 2 * 1024 * 1024
_MAX_STDERR = 64 * 1024
_MAX_PROMPT = 256 * 1024
_ENV_ALLOW = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "TEMP", "TMP", "TMPDIR",
    "LANG", "LC_ALL", "LC_CTYPE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "CODEX_HOME", "CODEX_CA_CERTIFICATE",
})
_DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "shell_snapshot", "remote_plugin", "plugins",
    "apps", "browser_use", "browser_use_external", "browser_use_full_cdp_access",
    "computer_use", "image_generation", "view_image", "multi_agent", "multi_agent_v2",
    "code_mode", "code_mode_host", "hooks", "memories", "goals", "sleep_tool",
    "skill_search", "skill_mcp_dependency_install", "workspace_dependencies",
)
_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["speak", "to", "content", "searchQuery"],
    "properties": {
        "speak": {"type": "boolean"},
        "to": {"type": "string", "enum": ["user", "deepseek", "gemini", "gpt", "grok", "paimon", "xiangling", "xiao", "zibai", "everyone"]},
        "content": {"type": "string"},
        "searchQuery": {"type": "string"},
    },
}


def _safe_error(raw: bytes | str) -> str:
    text = raw.decode("utf-8", errors="replace").lower() if isinstance(raw, bytes) else raw.lower()
    if any(word in text for word in ("401", "unauthorized", "authentication", "not logged in", "refresh token", "sign in")):
        return "Codex 登录已失效，请在 Codex 中重新使用 ChatGPT 登录。"
    if any(word in text for word in ("429", "usage limit", "rate limit", "quota", "credits", "limit reached")):
        return "Codex 使用额度不足或请求过于频繁，请稍后重试。"
    if any(word in text for word in ("model_not_found", "unsupported model", "model is not supported", "model does not exist")):
        return "当前 Codex 账户无法使用所选模型，请检查模型设置。"
    return "Codex 调用失败，请检查本机 Codex 登录和网络后重试。"


def _terminate_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        taskkill = str(Path(system_root) / "System32" / "taskkill.exe")
        try:
            subprocess.run([taskkill, "/PID", str(process.pid), "/T", "/F"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=3, creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _windows_job(process: subprocess.Popen):
    """Keep descendants tied to the request even if a CLI launcher exits first."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        return None
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    handle = kernel.OpenProcess(0x0101, False, process.pid)  # SET_QUOTA | TERMINATE
    assigned = bool(handle and kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                    and kernel.AssignProcessToJobObject(job, handle))
    if handle:
        kernel.CloseHandle(handle)
    if not assigned:
        kernel.CloseHandle(job)
        return None
    return lambda: kernel.CloseHandle(job)


def _run(command: list[str], env: Mapping[str, str], cwd: str, cancel: threading.Event,
         timeout: float, input_data: bytes = b"") -> tuple[int, bytes, bytes]:
    """Bound both streams and keep cancellation live while stdin writes block."""
    if cancel.is_set():
        raise CodexCancelled("已停止本次生成。")
    deadline = time.monotonic() + timeout
    try:
        process = subprocess.Popen(command, cwd=cwd, env=dict(env), shell=False,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   bufsize=0, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                   start_new_session=os.name != "nt")
    except (OSError, ValueError):
        raise CodexError("无法启动本机 Codex，请检查 CLI 安装。") from None
    job_cleanup = _windows_job(process)
    stopped = threading.Event()
    chunks: queue.Queue = queue.Queue(maxsize=32)

    def put(item):
        while not stopped.is_set():
            try:
                chunks.put(item, timeout=0.05)
                return
            except queue.Full:
                pass

    def read_stream(name, stream):
        try:
            while not stopped.is_set():
                data = stream.read(8192)
                if not data:
                    break
                put((name, data))
        except (OSError, ValueError):
            pass
        finally:
            put((name, None))

    def write_prompt():
        try:
            view = memoryview(input_data)
            while view and not stopped.is_set():
                count = process.stdin.write(view[:8192])
                if not count:
                    break
                view = view[count:]
        except (OSError, ValueError):
            pass
        finally:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass

    workers = [threading.Thread(target=read_stream, args=("out", process.stdout), daemon=True),
               threading.Thread(target=read_stream, args=("err", process.stderr), daemon=True),
               threading.Thread(target=write_prompt, daemon=True)]
    for worker in workers:
        worker.start()
    output, errors = bytearray(), bytearray()
    closed = set()
    try:
        while len(closed) < 2 or process.poll() is None:
            if cancel.is_set():
                raise CodexCancelled("已停止本次生成。")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CodexError("Codex 响应超时，请稍后重试。")
            try:
                name, data = chunks.get(timeout=min(0.05, remaining))
            except queue.Empty:
                continue
            if data is None:
                closed.add(name)
                continue
            target, maximum = (output, _MAX_STDOUT) if name == "out" else (errors, _MAX_STDERR)
            if len(target) + len(data) > maximum:
                raise CodexError("Codex 返回的数据过大，已停止本次生成。")
            target.extend(data)
        return process.returncode, bytes(output), bytes(errors)
    finally:
        stopped.set()
        if job_cleanup:
            job_cleanup()
        _terminate_tree(process)
        for worker in workers:
            worker.join(timeout=0.5)
        for stream in (process.stdin, process.stdout, process.stderr):
            try:
                stream.close()
            except (OSError, ValueError):
                pass


def _logged_in(executable: str, env: Mapping[str, str], cwd: str,
               cancel: threading.Event, timeout: float) -> bool:
    code, out, err = _run([executable, "login", "status"], env, cwd, cancel, timeout)
    # No forced_login_method here: mismatched forced auth can log a user out.
    text = (out + b"\n" + err).decode("utf-8", errors="replace")
    return code == 0 and bool(re.search(r"(?im)^\s*Logged in using ChatGPT\s*$", text))


def _extract_response(output: bytes) -> str:
    last = None
    complete = False
    try:
        for line in output.decode("utf-8-sig").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise ValueError()
            if event["type"] in ("error", "turn.failed"):
                raise CodexError(_safe_error(json.dumps(event)))
            if event["type"] == "turn.completed":
                complete = True
            item = event.get("item")
            if event["type"] == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
                if not isinstance(item.get("text"), str):
                    raise ValueError()
                last = item["text"].strip()
    except (ValueError, UnicodeError):
        raise CodexError("Codex 返回了无效的响应数据，请重试。") from None
    if not complete or not last:
        raise CodexError("Codex 未返回完整回答，请重试。")
    return last


@dataclass(frozen=True)
class CodexConnection:
    executable: str | None
    configured: bool
    detail: str
    model: str | None = None
    _env: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self):
        object.__setattr__(self, "_env", MappingProxyType({key: value for key, value in self._env.items() if key.upper() in _ENV_ALLOW}))

    def status(self) -> dict:
        return {"id": "gpt", "name": "GPT", "configured": self.configured,
                "model": self.model or "Codex 默认模型", "source": "codex", "detail": self.detail}

    def respond(self, prompt: str, cancel: threading.Event, timeout: float = 90, *,
                reasoning_effort: str = "medium") -> str:
        if cancel.is_set():
            raise CodexCancelled("已停止本次生成。")
        if not self.configured or not self.executable:
            raise CodexError(self.detail)
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > _MAX_PROMPT:
            raise CodexError("发送给 Codex 的上下文为空或过长。")
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise CodexError("Codex 超时设置无效。")
        if reasoning_effort not in ("medium", "high"):
            raise CodexError("Codex 文字思考级别无效。")
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="tavern-codex-") as directory:
            if not _logged_in(self.executable, self._env, directory, cancel, min(timeout, 10)):
                raise CodexError("请先在本机 Codex 中使用 ChatGPT 登录；此连接不使用 API Key。")
            schema = Path(directory) / "response.schema.json"
            schema.write_text(json.dumps(_SCHEMA), encoding="utf-8")
            command = [self.executable, "exec", "--json", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                       "--sandbox", "read-only", "--skip-git-repo-check", "--color", "never",
                       "--output-schema", str(schema)]
            config = {"approval_policy": "never", "web_search": "disabled", "project_doc_max_bytes": 0,
                      "apps._default.enabled": False, "features.skip_host_skill_discovery": True,
                      "features.fast_mode": True, "service_tier": "fast",
                      "model_reasoning_effort": reasoning_effort, "model_reasoning_summary": "none",
                      "developer_instructions": "You are the execution model for one assigned participant in a multi-model group chat. Follow the supplied room and character instructions. Transport names such as GPT or Codex do not replace the assigned character identity. In fictional roleplay, speak as that character without taking over other participants. Answer the supplied conversation only. If the room instructions permit research and a relevant real-world term, setting, or factual premise is unclear, request focused research with speak=false and a concise public searchQuery instead of guessing. Otherwise searchQuery is an empty string. Do not access files, run commands, use tools, or act as a coding agent. Return only the requested JSON decision. Do not expose hidden chain-of-thought."}
            config.update({f"features.{name}": False for name in _DISABLED_FEATURES})
            for name, value in config.items():
                command += ["-c", name + "=" + json.dumps(value)]
            if self.model:
                command += ["--model", self.model]
            command.append("-")
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise CodexError("Codex 响应超时，请稍后重试。")
            code, out, err = _run(command, self._env, directory, cancel, remaining, prompt.encode("utf-8"))
            if code != 0:
                raise CodexError(_safe_error(err + out))
            return _extract_response(out)


def discover(env: Mapping[str, str] | None = None, model: str | None = None) -> CodexConnection:
    """Read-only CLI discovery. Never opens auth files or changes user config."""
    source = dict(os.environ if env is None else env)
    child_env = {key: value for key, value in source.items() if key.upper() in _ENV_ALLOW}
    safe_model = model if isinstance(model, str) and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", model) else None
    executable = source.get("CODEX_CLI_PATH") or shutil.which("codex", path=source.get("PATH", ""))
    if not executable and source.get("LOCALAPPDATA"):
        candidate = Path(source["LOCALAPPDATA"]) / "Programs" / "codex" / "bin" / "codex.exe"
        if candidate.is_file():
            executable = str(candidate)
    if not executable or not Path(executable).is_file() or (os.name == "nt" and Path(executable).suffix.lower() != ".exe"):
        return CodexConnection(None, False, "未找到本机 Codex CLI，请先安装 Codex 并使用 ChatGPT 登录。", safe_model, child_env)
    try:
        with tempfile.TemporaryDirectory(prefix="tavern-codex-check-") as directory:
            cancel = threading.Event()
            code, help_text, _ = _run([executable, "exec", "--help"], child_env, directory, cancel, 5)
            required = (b"--ignore-user-config", b"--ignore-rules", b"--ephemeral", b"--output-schema", b"--json")
            if code or any(flag not in help_text for flag in required):
                return CodexConnection(executable, False, "本机 Codex CLI 版本过旧，请更新后刷新连接。", safe_model, child_env)
            configured = _logged_in(executable, child_env, directory, cancel, 5)
        detail = "通过本机 Codex 的 ChatGPT 登录连接，无需 API Key。" if configured else "请先在本机 Codex 中使用 ChatGPT 登录；此连接不使用 API Key。"
    except CodexError as exc:
        configured, detail = False, str(exc)
    return CodexConnection(executable, configured, detail, safe_model, child_env)
