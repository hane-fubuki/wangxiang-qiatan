"""Private model transports. API credentials never cross the HTTP app boundary.

Prefer the user's existing Codex stdio MCP servers. No credentials are extracted
from their stores. A request owns its subprocess, so cancellation and deadlines
can stop a blocked transport without leaving a network worker behind.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import tomllib
from typing import Any
import urllib.error
import urllib.request

if __package__:
    from backend.local_connection import LocalConnection, MODEL_PATTERN, validated_url
else:
    from local_connection import LocalConnection, MODEL_PATTERN, validated_url


class GatewayError(RuntimeError):
    """A display-safe model error, never the upstream raw error body."""


class CancelledError(GatewayError):
    """The caller cancelled its request."""


PROVIDERS = {
    "deepseek": {"name": "DeepSeek", "model": "deepseek-flash"},
    "gemini": {"name": "Gemini", "model": "gemini-3.8-flash"},
    "gpt": {"name": "GPT", "model": "gpt-6.1-sol"},
    "grok": {"name": "Grok", "model": "grok-4.7"},
    "custom": {"name": "自定义 API", "model": "gemini-4-argon"},
}
_MAX_LINE_BYTES = 4 * 1024 * 1024
_ENV_NAMES = {
    "DEEPSEEK_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_MODEL", "GEMINI_MODEL",
    "GROK_API_KEY", "XAI_API_KEY", "GROK_MODEL",
    "MODEL_TIMEOUT_SECONDS",
}


def _reasoning_fields(provider_id: str, model: str, effort: str) -> dict[str, Any]:
    """Use documented model parameters, leaving unknown/custom models alone.

    App levels are medium/high. DeepSeek maps both to its native high level;
    max is deliberately not selected implicitly. Gemini 2.5 uses a budget,
    while Gemini 3/4 and the newer Grok models use effort levels.
    """
    if provider_id == "deepseek" and model in {"deepseek-flash", "deepseek-v4-pro", "deepseek-v4-flash"}:
        return {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}
    if provider_id == "gemini":
        if model in {"gemini-4-argon", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
                     "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.1-pro-preview",
                     "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"}:
            return {"thinkingLevel": effort, "includeThoughts": False}
        if model == "gemini-3-pro-preview":
            return {"thinkingLevel": "high", "includeThoughts": False}
        if model in {"gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"}:
            return {"thinkingBudget": 8192 if effort == "high" else 4096, "includeThoughts": False}
    if provider_id == "grok" and re.fullmatch(r"grok-4\.[567](?:-(?:latest|\d{8}|\d{4}-\d{2}-\d{2}))?", model):
        return {"reasoning_effort": effort}
    return {}


def _output_budget(provider_id: str, model: str, effort: str) -> int:
    # These caps include hidden thinking tokens. 4096 could exhaust the entire
    # budget before an answer exists. Unknown models retain the old safe cap.
    return (32768 if effort == "high" else 16384) if _reasoning_fields(provider_id, model, effort) else 4096


def _validate_reasoning(effort: Any) -> str:
    if not isinstance(effort, str) or effort not in {"medium", "high"}:
        raise GatewayError("思考强度只能选择 medium 或 high。")
    return effort


def _mcp_arguments(provider_id: str, model: str, prompt: str, effort: str, schema: Any) -> dict[str, Any]:
    """Only use optional MCP arguments advertised by this running bridge."""
    arguments = {"prompt": prompt, "model": model, "max_output_tokens": 4096}
    if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict):
        return arguments
    properties = schema["properties"]
    token_schema = properties.get("max_output_tokens")
    if isinstance(token_schema, dict) and token_schema.get("type") == "integer":
        maximum = token_schema.get("maximum", 32768)
        if isinstance(maximum, (int, float)) and not isinstance(maximum, bool) and 1 <= maximum <= 393216:
            arguments["max_output_tokens"] = min(_output_budget(provider_id, model, effort), int(maximum))
    effort_schema = properties.get("reasoning_effort")
    if _reasoning_fields(provider_id, model, effort) and isinstance(effort_schema, dict) and effort_schema.get("type") == "string":
        choices = effort_schema.get("enum")
        if choices is None or isinstance(choices, list) and effort in choices:
            arguments["reasoning_effort"] = effort
        elif provider_id == "deepseek" and isinstance(choices, list) and "high" in choices:
            arguments["reasoning_effort"] = "high"
    return arguments


@dataclass(frozen=True)
class _Settings:
    env: dict[str, str] = field(repr=False)
    servers: dict[str, Any] = field(repr=False)
    config_error: bool
    timeout: float
    codex: Any = field(repr=False)
    custom: dict[str, str] = field(default_factory=dict, repr=False)


def _dotenv(path: Path) -> dict[str, str]:
    """Read only supported settings; do not execute shell syntax/interpolation."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        name, separator, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if separator and name in _ENV_NAMES:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            else:
                value = value.split(" #", 1)[0].rstrip()
            values[name] = value
    return values


def _safe_error(raw: Any) -> str:
    """Classify diagnostics, never return arbitrary server/credential content."""
    text = str(raw).lower()
    if any(word in text for word in ("output reached the token limit", "思考或回答达到长度上限")):
        return "模型思考或回答达到长度上限，请缩短问题后重试。"
    if any(word in text for word in ("401", "403", "unauthenticated", "permission_denied", "api key", "api_key", "authentication", "身份验证")):
        return "身份验证失败，请检查本机 API 凭据或访问权限。"
    if any(word in text for word in ("429", "quota", "rate limit", "resource_exhausted", "insufficient balance", "402", "额度不足")):
        return "额度不足或请求过于频繁，请稍后重试并检查账户额度。"
    if any(word in text for word in ("404", "model_not_found", "not found", "unsupported model", "模型不存在")):
        return "模型不存在或当前账户无法使用，请检查模型名称。"
    if any(word in text for word in ("timeout", "timed out", "超时")):
        return "模型响应超时，请稍后重试。"
    if any(word in text for word in ("500", "502", "503", "overloaded", "unavailable", "服务暂时不可用")):
        return "模型服务暂时不可用，请稍后重试。"
    return "模型调用失败，请检查本机连接配置和网络后重试。"


class _JsonProcess:
    """Small newline-delimited JSON transport with bounded, cancellable reads."""

    def __init__(self, command: list[str], env: dict[str, str], cwd: str | None = None):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=env, cwd=cwd,
                creationflags=flags,
            )
        except (OSError, ValueError):
            raise GatewayError("无法启动本机模型连接，请检查 MCP 启动程序。") from None
        self.lines: queue.Queue[Any] = queue.Queue(maxsize=16)
        self.closed = threading.Event()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _put(self, item: Any) -> None:
        while not self.closed.is_set():
            try:
                self.lines.put(item, timeout=0.1)
                return
            except queue.Full:
                pass

    def _read(self) -> None:
        try:
            assert self.process.stdout is not None
            while not self.closed.is_set():
                line = self.process.stdout.readline(_MAX_LINE_BYTES + 1)
                if not line:
                    break
                if len(line) > _MAX_LINE_BYTES:
                    self._put(GatewayError("模型连接返回的数据过大。"))
                    break
                try:
                    message = json.loads(line.decode("utf-8-sig"))
                except (ValueError, UnicodeError):
                    self._put(GatewayError("模型连接返回了无效的 JSON 数据。"))
                    break
                if isinstance(message, dict):
                    self._put(message)
        except (OSError, ValueError):
            pass
        finally:
            self._put(None)

    def send(self, message: dict[str, Any]) -> None:
        try:
            assert self.process.stdin is not None
            self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
            self.process.stdin.flush()
        except (OSError, ValueError):
            raise GatewayError("本机模型连接已关闭，请重试。") from None

    def receive(self, request_id: int, cancel: threading.Event, deadline: float) -> dict[str, Any]:
        while True:
            if cancel.is_set():
                raise CancelledError("已停止本次生成。")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GatewayError("模型响应超时，请稍后重试。")
            try:
                message = self.lines.get(timeout=min(0.1, remaining))
            except queue.Empty:
                continue
            if message is None:
                raise GatewayError("本机模型连接意外退出，请检查 MCP 配置。")
            if isinstance(message, GatewayError):
                raise message
            if message.get("id") != request_id:
                continue  # MCP progress/log notifications are not responses.
            if "error" in message:
                raise GatewayError(_safe_error(message["error"]))
            result = message.get("result")
            if not isinstance(result, dict):
                raise GatewayError("模型连接返回了无效的响应。")
            return result

    def close(self) -> None:
        self.closed.set()
        if self.process.poll() is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.reader.join(timeout=1)
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                stream.close()


class ModelGateway:
    supports_reasoning_options = True

    def __init__(
        self, config_path: Path | str | None = None,
        env: dict[str, str] | None = None,
        dotenv_path: Path | str | None = None,
        timeout: float | None = None,
        connection_path: Path | str | None = None,
        catalog_path: Path | str | None = None,
    ) -> None:
        self._dotenv_path = Path(dotenv_path) if dotenv_path else Path(__file__).resolve().parents[1] / ".env"
        self.local_connection = LocalConnection(connection_path or self._dotenv_path.parent / ".tavern" / "model-connection.bin")
        self._catalog_path = Path(catalog_path) if catalog_path else Path(__file__).resolve().parents[1] / "模型选项.json"
        self._explicit_env = dict(env) if env is not None else None
        self._explicit_config = Path(config_path) if config_path else None
        self._explicit_timeout = timeout
        self.refresh()

    @property
    def timeout(self) -> float:
        return self._settings.timeout

    def refresh(self) -> list[dict[str, Any]]:
        """Reload settings and atomically replace the snapshot used by new calls.

        An in-flight request retains its original model, transport, and deadline.
        Explicit constructor overrides remain fixed; process env is re-read only
        if the caller did not supply a test/override env mapping.
        """
        env = _dotenv(self._dotenv_path)
        env.update(os.environ if self._explicit_env is None else self._explicit_env)
        default_config = Path(env.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
        config_path = self._explicit_config or default_config
        config_error = False
        config = {}
        try:
            with config_path.open("rb") as stream:
                config = tomllib.load(stream)
                servers = config.get("mcp_servers", {})
        except FileNotFoundError:
            servers = {}
        except (OSError, ValueError):
            servers = {}
            config_error = True
        if not isinstance(servers, dict):
            servers = {}
            config_error = True
        try:
            configured_timeout = float(env.get("MODEL_TIMEOUT_SECONDS", "180"))
        except ValueError:
            configured_timeout = 180
        timeout = max(0.1, min(float(self._explicit_timeout if self._explicit_timeout is not None else configured_timeout), 300))
        from backend.codex_provider import discover
        # The tavern selects Sol independently; Codex still owns its login state.
        codex = discover(env, model=PROVIDERS["gpt"]["model"])
        try:
            custom = self.local_connection.load()
        except ValueError:
            custom = {}
        self._settings = _Settings(env, servers, config_error, timeout, codex, custom)
        return self.status()

    def _server(self, provider_id: str, settings: _Settings) -> dict[str, Any] | None:
        if provider_id == "custom":
            return None
        server = settings.servers.get(provider_id)
        if not isinstance(server, dict) or server.get("enabled", True) is False:
            return None
        if not isinstance(server.get("command"), str) or not server["command"].strip():
            return None
        args = server.get("args", [])
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            return None
        return server

    def _model(self, provider_id: str, settings: _Settings) -> str:
        if provider_id == "custom":
            return settings.custom.get("model", PROVIDERS["custom"]["model"])
        candidate = settings.env.get(provider_id.upper() + "_MODEL", "").strip().removeprefix("models/")
        return candidate or PROVIDERS[provider_id]["model"]

    def _key(self, provider_id: str, settings: _Settings) -> str:
        if provider_id == "custom":
            return settings.custom.get("apiKey", "")
        key = settings.env.get(provider_id.upper() + "_API_KEY", "").strip()
        return key or (settings.env.get("XAI_API_KEY", "").strip() if provider_id == "grok" else "")

    def status(self) -> list[dict[str, Any]]:
        settings = self._settings
        result = []
        for provider_id, info in PROVIDERS.items():
            if provider_id == "gpt":
                result.append(settings.codex.status())
                continue
            server = self._server(provider_id, settings)
            has_key = bool(self._key(provider_id, settings))
            source = "mcp" if server else "api" if has_key else "none"
            detail = {
                "mcp": "已读取本机 MCP 配置，发送消息时连接。",
                "api": "已读取本地 API 环境变量，发送消息时连接。",
                "none": "请配置本机 MCP 连接，或在 .env 中填写 API Key。",
            }[source]
            if settings.config_error and source == "none":
                detail = "无法读取本机 MCP 配置，请检查 config.toml 或配置 .env。"
            if provider_id == "custom":
                detail = "使用单独保存的兼容 API；仅对明确选择此连接的角色生效。" if has_key else "在本机模型连接设置中填写兼容 API。"
            result.append({"id": provider_id, "name": info["name"], "configured": source != "none", "model": self._model(provider_id, settings), "detail": detail, "source": source})
        return result

    def model_options(self) -> list[dict[str, Any]]:
        """Public model choices contain no credentials or local configuration."""
        statuses = self.status()
        result = []
        labels = {
            "deepseek-v4-pro": "DeepSeek V4 Pro",
            "gemini-3.8-flash": "Gemini 3.8 Flash",
            "gemini-4-argon": "Gemini 4 Argon",
            "gpt-6.1-sol": "GPT · Sol",
            "grok-4.7": "Grok 4.7",
        }
        for status in statuses:
            provider_id = status["id"]
            # The Gemini routes used by the trio remain selectable even when a
            # local default override is configured for the ordinary chat room.
            models = [status["model"]]
            if provider_id == "gemini":
                models.extend(("gemini-3.8-flash", "gemini-4-argon"))
            for model in dict.fromkeys(models):
                result.append({"providerId": provider_id, "model": model,
                               "name": labels.get(model, f"{status['name']} · {model}"),
                               "configured": status["configured"]})
        # An optional catalog adds choices without replacing working defaults.
        try:
            if self._catalog_path.stat().st_size > 64 * 1024:
                raise ValueError
            catalog = json.loads(self._catalog_path.read_text(encoding="utf-8-sig"))
            if not isinstance(catalog, list) or len(catalog) > 100:
                raise ValueError
        except FileNotFoundError:
            catalog = []
        except (OSError, ValueError, UnicodeError):
            raise GatewayError("模型选项文件格式不正确，请检查模型选项.json。") from None
        known = {status["id"]: status for status in statuses}
        seen = {(item["providerId"], item["model"]) for item in result}
        for item in catalog:
            if not isinstance(item, dict) or set(item) != {"providerId", "model", "name"}:
                raise GatewayError("模型选项只能包含提供商、模型编号和显示名称。")
            provider, model, name = item["providerId"], item["model"], item["name"]
            if (not isinstance(provider, str) or provider not in known or not isinstance(model, str)
                    or not re.fullmatch(MODEL_PATTERN, model) or not isinstance(name, str)
                    or not 1 <= len(name.strip()) <= 100 or any(ord(c) < 32 for c in name)):
                raise GatewayError("模型选项包含无效提供商、模型编号或名称。")
            if (provider, model) not in seen:
                result.append({"providerId": provider, "model": model, "name": name.strip(), "configured": known[provider]["configured"]})
                seen.add((provider, model))
        return result

    def _route(self, room_id: str, slot: str, assignments: dict | None = None) -> tuple[str, str | None]:
        from backend.rooms import get_room, model_route
        default = model_route(room_id, slot)  # Validate the persistent slot first.
        if assignments is None:
            return default
        if not isinstance(assignments, dict):
            raise GatewayError("角色模型配置格式不正确。")
        characters = get_room(room_id)["characters"]
        allowed = {(option["providerId"], option["model"]) for option in self.model_options()}
        for assigned_slot, choice in assignments.items():
            if assigned_slot not in characters:
                raise GatewayError("未知的聊天室角色。")
            if not isinstance(choice, dict):
                raise GatewayError("角色模型配置格式不正确。")
            provider_id, model = choice.get("providerId"), choice.get("model")
            if not isinstance(provider_id, str) or provider_id not in PROVIDERS:
                raise GatewayError("不支持的模型提供商。")
            if not isinstance(model, str) or not re.fullmatch(MODEL_PATTERN, model):
                raise GatewayError("模型名称格式不正确。")
            if (provider_id, model) not in allowed:
                raise GatewayError("该模型不在当前可选列表中，请刷新模型连接后重选。")
        choice = assignments.get(slot)
        return (choice["providerId"], choice["model"]) if choice is not None else default

    def room_status(self, room_id: str, assignments: dict | None = None) -> list[dict[str, Any]]:
        """Expose current transport status under each room's persistent slots."""
        from backend.rooms import get_room
        room = get_room(room_id)
        statuses = {item["id"]: item for item in self.status()}
        result = []
        for slot in room["characters"]:
            provider_id, model = self._route(room_id, slot, assignments)
            status = dict(statuses[provider_id])
            status.update(id=slot, providerId=provider_id, model=model or status["model"])
            result.append(status)
        return result

    def respond_for(self, room_id: str, slot: str, prompt: str, cancel: threading.Event | None = None, assignments: dict | None = None, *, reasoning_effort: str = "medium") -> str:
        """Call a character's model without changing its history or reply slot."""
        provider_id, model = self._route(room_id, slot, assignments)
        return self.respond(provider_id, prompt, cancel, model=model, reasoning_effort=reasoning_effort)

    def respond(self, provider_id: str, prompt: str, cancel: threading.Event | None = None, *, model: str | None = None, reasoning_effort: str = "medium") -> str:
        settings = self._settings
        reasoning_effort = _validate_reasoning(reasoning_effort)
        if provider_id not in PROVIDERS:
            raise GatewayError("不支持的模型提供商。")
        if not isinstance(prompt, str) or not prompt.strip():
            raise GatewayError("消息不能为空。")
        if len(prompt) > 200_000:
            raise GatewayError("本次上下文过长，请缩短消息或新建讨论。")
        cancel = cancel or threading.Event()
        if cancel.is_set():
            raise CancelledError("已停止本次生成。")
        if model is not None:
            if not isinstance(model, str):
                raise GatewayError("模型名称格式不正确。")
            model = model.strip().removeprefix("models/")
            if not re.fullmatch(MODEL_PATTERN, model):
                raise GatewayError("模型名称格式不正确。")
        if provider_id == "gpt":
            from backend.codex_provider import CodexError, CodexCancelled
            try:
                connection = replace(settings.codex, model=model) if model is not None else settings.codex
                return connection.respond(prompt, cancel, settings.timeout, reasoning_effort=reasoning_effort)
            except CodexCancelled as exc:
                raise CancelledError(str(exc)) from None
            except CodexError as exc:
                raise GatewayError(str(exc)) from None
        model = model if model is not None else self._model(provider_id, settings)
        if not re.fullmatch(MODEL_PATTERN, model):
            raise GatewayError("模型名称格式不正确，请检查 .env。")
        server = self._server(provider_id, settings)
        deadline = time.monotonic() + settings.timeout
        if server:
            return self._respond_mcp(provider_id, model, prompt, server, cancel, deadline, reasoning_effort)
        key = self._key(provider_id, settings)
        if not key:
            raise GatewayError(f"{PROVIDERS[provider_id]['name']} 尚未配置，请连接本机 MCP 或填写 API Key。")
        transport = _JsonProcess([sys.executable, str(Path(__file__).resolve()), "--direct"], dict(os.environ))
        try:
            decision_json = "<conversation_data>" in prompt and '"speak"' in prompt and "请仅返回一个 JSON 对象" in prompt
            payload = {"provider": provider_id, "model": model, "prompt": prompt, "key": key, "timeout": settings.timeout, "json_mode": decision_json, "reasoning_effort": reasoning_effort}
            if provider_id == "custom":
                payload["compatible_url"] = settings.custom["baseUrl"]
            transport.send(payload)
            result = transport.receive(1, cancel, deadline)
            return _extract_text(result)
        finally:
            transport.close()

    def _respond_mcp(self, provider_id: str, model: str, prompt: str, server: dict[str, Any], cancel: threading.Event, deadline: float, reasoning_effort: str = "medium") -> str:
        process_env = dict(os.environ)
        server_env = server.get("env", {})
        if isinstance(server_env, dict):
            process_env.update({str(key): str(value) for key, value in server_env.items()})
        transport = _JsonProcess([server["command"], *server.get("args", [])], process_env, server.get("cwd"))
        try:
            transport.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "wisdom-tavern", "version": "1.0.0"}}})
            initialized = transport.receive(1, cancel, min(deadline, time.monotonic() + 15))
            transport.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            if cancel.is_set():
                raise CancelledError("已停止本次生成。")
            schema = None
            capabilities = initialized.get("capabilities", {})
            if isinstance(capabilities, dict) and isinstance(capabilities.get("tools"), dict):
                transport.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
                try:
                    listed = transport.receive(2, cancel, min(deadline, time.monotonic() + 3))
                    tools = listed.get("tools", [])
                    if isinstance(tools, list):
                        schema = next((tool.get("inputSchema") for tool in tools if isinstance(tool, dict) and tool.get("name") == "ask_" + provider_id), None)
                except CancelledError:
                    raise
                except GatewayError:
                    # Legacy bridges may not implement tools/list. Do not send
                    # new options or make a second paid request in that case.
                    pass
            arguments = _mcp_arguments(provider_id, model, prompt, reasoning_effort, schema)
            transport.send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ask_" + provider_id, "arguments": arguments}})
            text = _extract_text(transport.receive(3, cancel, deadline))
            return _repair_deepseek_text(text) if provider_id == "deepseek" else text
        finally:
            transport.close()


def _extract_text(result: dict[str, Any]) -> str:
    if result.get("isError"):
        raise GatewayError(_safe_error(result.get("content", "")))
    content = result.get("content", [])
    if not isinstance(content, list):
        raise GatewayError("模型返回了无效的消息格式。")
    text = "\n".join(part["text"] for part in content if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)).strip()
    if not text:
        raise GatewayError("模型没有返回文本，请重新尝试。")
    return text


def _repair_deepseek_text(text: str) -> str:
    """Repair the local Windows PowerShell bridge's missing HTTP charset.

    Some DeepSeek responses arrive as UTF-8 bytes decoded as Latin-1 by Windows
    PowerShell's Invoke-RestMethod. Repair only a strict, fully reversible
    conversion with recognizable CJK/emoji output. Already-correct Unicode or
    ordinary accented Latin text is left untouched; no lossy replacement occurs.
    This workaround belongs only to that provider's MCP transport.
    """
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return text
    if repaired == text:
        return text
    if not re.search(r"[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef\U0001f000-\U0001faff]", repaired):
        return text
    if repaired.encode("utf-8").decode("latin-1") != text:
        return text
    return repaired


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a user-saved Authorization header to another endpoint.
        raise urllib.error.HTTPError(req.full_url, code, "redirect denied", headers, fp)


def _direct_response(payload: dict[str, Any]) -> str:
    """Official REST fallback; called only in the disposable child process."""
    provider_id, model, prompt, key = (payload[k] for k in ("provider", "model", "prompt", "key"))
    effort = _validate_reasoning(payload.get("reasoning_effort", "medium"))
    reasoning = _reasoning_fields(provider_id, model, effort)
    budget = _output_budget(provider_id, model, effort)
    headers = {"Content-Type": "application/json"}
    if provider_id == "custom":
        try:
            url = validated_url(payload.get("compatible_url")) + "/chat/completions"
        except ValueError:
            raise GatewayError("自定义 API 地址无效，请重新配置。") from None
        headers["Authorization"] = "Bearer " + key
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "max_tokens": budget}
        if payload.get("json_mode"):
            body["response_format"] = {"type": "json_object"}
    elif provider_id in ("deepseek", "grok"):
        url = "https://api.x.ai/v1/chat/completions" if provider_id == "grok" else "https://api.deepseek.com/chat/completions"
        headers["Authorization"] = "Bearer " + key
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "max_tokens": budget}
        body.update(reasoning)
        if payload.get("json_mode"):
            body["response_format"] = {"type": "json_object"}
    elif provider_id == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers["x-goog-api-key"] = key
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": budget}}
        if reasoning:
            body["generationConfig"]["thinkingConfig"] = reasoning
        if payload.get("json_mode"):
            body["generationConfig"]["responseMimeType"] = "application/json"
    else:
        raise GatewayError("不支持的模型提供商。")
    request = urllib.request.Request(url, json.dumps(body, ensure_ascii=False).encode("utf-8"), headers, method="POST")
    try:
        opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open
                  if provider_id == "custom" else urllib.request.urlopen)
        with opener(request, timeout=float(payload.get("timeout", 90))) as response:
            raw = response.read(_MAX_LINE_BYTES + 1)
        if len(raw) > _MAX_LINE_BYTES:
            raise GatewayError("模型返回的数据过大。")
        result = json.loads(raw)
        if provider_id in ("deepseek", "grok", "custom"):
            if result["choices"][0].get("finish_reason") == "length":
                raise GatewayError("模型思考或回答达到长度上限，请缩短问题后重试。")
            text = result["choices"][0]["message"]["content"]
        else:
            if result["candidates"][0].get("finishReason") == "MAX_TOKENS":
                raise GatewayError("模型思考或回答达到长度上限，请缩短问题后重试。")
            text = "\n".join(part["text"] for part in result["candidates"][0]["content"]["parts"] if isinstance(part.get("text"), str) and not part.get("thought"))
        if not isinstance(text, str) or not text.strip():
            raise GatewayError("模型没有返回文本，请重新尝试。")
        return text.strip()
    except urllib.error.HTTPError as error:
        message = _safe_error(error.code)
        error.close()
        raise GatewayError(message) from None
    except (urllib.error.URLError, OSError) as error:
        raise GatewayError(_safe_error(error)) from None
    except (KeyError, IndexError, TypeError, ValueError):
        raise GatewayError("模型返回了无效的消息格式。") from None


def _direct_main() -> None:
    try:
        payload = json.loads(sys.stdin.buffer.readline(_MAX_LINE_BYTES))
        text = _direct_response(payload)
        reply = {"id": 1, "result": {"content": [{"type": "text", "text": text}]}}
    except GatewayError as error:
        reply = {"id": 1, "result": {"isError": True, "content": [{"type": "text", "text": str(error)}]}}
    except Exception:
        reply = {"id": 1, "error": {"message": "request failed"}}
    sys.stdout.buffer.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__" and sys.argv[1:] == ["--direct"]:
    _direct_main()
