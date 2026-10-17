"""An explicitly selected compatible API, encrypted for the current Windows user."""
from __future__ import annotations

import ctypes
import ipaddress
import json
import os
from pathlib import Path
import re
import threading
from urllib.parse import unquote, urlsplit, urlunsplit

DEFAULT_MODEL = "gemini-4-argon"
MODEL_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}"
MAX_CONFIG_BYTES = 32 * 1024


def validated_url(value):
    message = "请填写 HTTPS API 基础地址（如 https://服务商域名/v1）；本机接口可用 HTTP。"
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise ValueError(message)
    value = value.strip().rstrip("/")
    try:
        parts = urlsplit(value)
        host, port = parts.hostname, parts.port
        decoded = unquote(value)
        if (not host or parts.username is not None or parts.password is not None or parts.query or parts.fragment
                or any(ord(c) <= 32 or ord(c) == 127 for c in decoded) or "\\" in decoded
                or parts.scheme not in {"https", "http"} or port is not None and not 1 <= port <= 65535):
            raise ValueError
        loopback = host in {"localhost", "127.0.0.1", "::1"}
        if parts.scheme != "https" and not loopback:
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", host):
                raise ValueError
            if re.fullmatch(r"[0-9.]+", host) or host.lower().startswith("0x"):
                raise ValueError
            if not loopback and ("." not in host or host.endswith((".local", ".localhost", ".internal", ".lan"))):
                raise ValueError
        else:
            if not address.is_global and not loopback:
                raise ValueError
        if any(segment in {".", ".."} for segment in unquote(parts.path).split("/")):
            raise ValueError
        if parts.path.rstrip("/").endswith("/chat/completions"):
            raise ValueError
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    except (ValueError, UnicodeError):
        raise ValueError(message) from None


class _Blob(ctypes.Structure):
    _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    if os.name != "nt":
        raise ValueError("安全凭据保存需要 Windows；现有模型连接仍可继续使用。")
    source_buffer = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = _Blob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError("无法读取或保存本机凭据，请在这台电脑重新填写。")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


class LocalConnection:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()

    def load(self):
        with self.lock:
            if not self.path.exists():
                return {}
            try:
                if self.path.is_symlink() or self.path.stat().st_size > MAX_CONFIG_BYTES:
                    raise ValueError
                value = json.loads(protect(self.path.read_bytes(), decrypt=True))
                if not isinstance(value, dict):
                    raise ValueError
                return self._validate(value)
            except (OSError, ValueError, UnicodeError, TypeError):
                raise ValueError("本机凭据无法读取，请重新填写并保存。") from None

    @staticmethod
    def _validate(data):
        url = validated_url(data.get("baseUrl"))
        key = data.get("apiKey")
        model = data.get("model", DEFAULT_MODEL)
        if not isinstance(key, str) or not 1 <= len(key) <= 8192 or any(ord(c) <= 32 or ord(c) >= 127 for c in key):
            raise ValueError("请填写有效的 API Key。")
        if not isinstance(model, str) or not re.fullmatch(MODEL_PATTERN, model):
            raise ValueError("请填写有效模型编号。")
        return {"baseUrl": url, "apiKey": key, "model": model}

    def metadata(self):
        try:
            value = self.load()
            return {"baseUrl": value.get("baseUrl", ""), "hasKey": bool(value.get("apiKey")),
                    "model": value.get("model", DEFAULT_MODEL), "providerId": "custom", "error": ""}
        except ValueError:
            return {"baseUrl": "", "hasKey": False, "model": DEFAULT_MODEL, "providerId": "custom",
                    "error": "本机凭据无法读取，请重新填写并保存。"}

    def prepare(self, data):
        if not isinstance(data, dict):
            raise ValueError("连接配置格式不正确。")
        url = validated_url(data.get("baseUrl"))
        key = data.get("apiKey", "")
        if not isinstance(key, str):
            raise ValueError("请填写有效的 API Key。")
        key = key.strip()
        if not key:
            old = self.load()
            if old.get("baseUrl") != url:
                raise ValueError("更换 API 地址时必须重新填写 API Key。")
            key = old.get("apiKey", "")
        return self._validate({"baseUrl": url, "apiKey": key, "model": data.get("model", DEFAULT_MODEL)})

    def save(self, data):
        with self.lock:
            value = self.prepare(data)
            try:
                encrypted = protect(json.dumps(value).encode("utf-8"))
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix(".tmp")
                temporary.write_bytes(encrypted)
                temporary.replace(self.path)
            except OSError:
                raise ValueError("无法保存本机凭据，请检查目录是否可写。") from None
        return self.metadata()

    def clear(self):
        with self.lock:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                raise ValueError("无法清除本机凭据，请检查目录权限。") from None

    def test(self, data):
        from backend.providers import _direct_response
        value = self.prepare(data)
        _direct_response({"provider": "custom", "model": value["model"], "prompt": "Reply only OK.",
                          "key": value["apiKey"], "compatible_url": value["baseUrl"], "timeout": 30})
        return {"ok": True, "message": "连接测试通过，配置尚未保存。"}
