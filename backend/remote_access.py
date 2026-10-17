"""Authenticated loopback reverse proxy for an HTTPS tunnel; standard library only.

The upstream address and route allowlist are fixed locally. This service does
not create a tunnel, change the main app, or expose a public listening socket.
"""
from __future__ import annotations

import argparse
from collections import deque
import getpass
import hashlib
import hmac
import http.client
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import secrets
import threading
import time
from urllib.parse import urlsplit
from backend import APP_NAME
from backend.releases import MAX_RELEASE_BYTES, RELEASE_FILENAME
from backend.visitors import COOKIE as VISITOR_COOKIE, cookie_identity, visitor_cookie


COOKIE_NAME = "__Host-tavern_session"
SESSION_TTL = 86400
MAX_BODY = 131072
MAX_UPLOAD = 8 * 1024 * 1024
MAX_RESPONSE = 32 * 1024 * 1024
_CID = r"[a-f0-9]{32}"
_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
_STATIC = {"/roscaelifer-theme.css", "/roscaelifer-icons.js", "/outer-ring-theme.css", "/outer-ring-icons.js", "/", "/index.html", "/app.js", "/styles.css", "/tea-theme.css", "/studio-theme.css", "/yunkui-theme.css", "/obol-theme.css", "/mockingbird-theme.css", "/mockingbird-icons.js", "/favicon.svg",
           "/assets/user-avatar.png", "/assets/tea-party-reference.jpg"}
_ASSETS = re.compile(r"/assets/(?:roscaelifer-(?:norma|velina|sigrid|claret|roxy|lindverne)-(?:stand|avatar)\.png|outer-ring-(?:burnice|caesar|lucy|lighter|pulchra|piper)-(?:stand|avatar)\.png|(?:deepseek|gemini|gpt|grok)-(?:stand\.png|avatar\.png|original\.jpg|avatar-reference\.png)|zzz-(?:sunna|nangong-yu|aria)-(?:stand|avatar)\.png|mockingbird-(?:vivian|hugo)-(?:stand|avatar)\.png|obol-(?:seed|magus|orphie|trigger|soldier11|silver-anby)-(?:stand|avatar)\.png|yunkui-(?:yixuan|ye-shunguang|pan-yinhu|ju-fufu)-(?:stand|avatar)\.png|krampus-(?:dialyn|zhao|phoenix|banyue|promeia)-(?:stand|avatar)\.png|wangsheng-(?:(?:gemini|deepseek|gpt)-(?:stand|avatar)\.png|(?:room|paimon|xiangling|xiao|zibai)\.png|(?:gemini|deepseek|gpt|paimon|xiangling|xiao|zibai)\.svg))")


def _validate_public_host(host):
    if not isinstance(host, str) or not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", host):
        raise ValueError("public_host 必须是无协议、无端口的小写公网域名。")


class _Auth:
    def __init__(self, password):
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise ValueError("远程访问密码须为 12 到 256 个字符。")
        self.salt = secrets.token_bytes(16)
        self.password_hash = self._hash(password)
        self.sessions: dict[str, float] = {}
        self.failures = deque()
        self.lock = threading.Lock()
        self._checking = 0

    def _hash(self, password):
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), self.salt, 310000)

    def _purge(self, now):
        for token, expiry in list(self.sessions.items()):
            if expiry <= now:
                del self.sessions[token]
        while self.failures and self.failures[0] <= now - 60:
            self.failures.popleft()

    def login(self, password):
        """Return (HTTP status, token); throttle globally behind the local tunnel."""
        now = time.monotonic()
        with self.lock:
            self._purge(now)
            if len(self.failures) + self._checking >= 8 or self._checking >= 2:
                return 429, None
            self._checking += 1
        try:
            candidate = password if isinstance(password, str) and len(password) <= 256 else ""
            try:
                candidate_hash = self._hash(candidate)
            except UnicodeError:
                candidate_hash = self._hash("")
            valid = hmac.compare_digest(candidate_hash, self.password_hash)
        except Exception:
            with self.lock:
                self._checking -= 1
            raise
        with self.lock:
            self._checking -= 1
            now = time.monotonic()
            self._purge(now)
            if not valid:
                self.failures.append(now)
                return 401, None
            if len(self.sessions) >= 256:
                del self.sessions[min(self.sessions, key=self.sessions.get)]
            token = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(token.encode("ascii")).hexdigest()] = now + SESSION_TTL
            return 200, token

    @staticmethod
    def cookie_token(headers):
        cookie_headers = headers.get_all("Cookie", [])
        if len(cookie_headers) != 1 or len(cookie_headers[0]) > 8192:
            return None
        # Reject duplicate auth-cookie assignments rather than relying on a
        # parser's first/last-value preference.
        if sum(part.strip().partition("=")[0] == COOKIE_NAME for part in cookie_headers[0].split(";")) != 1:
            return None
        jar = SimpleCookie()
        try:
            jar.load(cookie_headers[0])
            token = jar[COOKIE_NAME].value
        except (CookieError, KeyError, ValueError):
            return None
        return token if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) else None

    def authorized(self, headers):
        token = self.cookie_token(headers)
        if token is None:
            return False
        key = hashlib.sha256(token.encode("ascii")).hexdigest()
        with self.lock:
            self._purge(time.monotonic())
            return key in self.sessions

    def logout(self, headers):
        token = self.cookie_token(headers)
        if token:
            with self.lock:
                self.sessions.pop(hashlib.sha256(token.encode("ascii")).hexdigest(), None)


class RemoteServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 32

    def __init__(self, address, handler):
        self._workers = threading.BoundedSemaphore(32)
        self._host_lock = threading.Lock()
        self._public_host = None
        super().__init__(address, handler)

    @property
    def public_host(self):
        with self._host_lock:
            return self._public_host

    def set_public_host(self, public_host):
        """Activate once, only after this proxy owns the tunnel's local port."""
        _validate_public_host(public_host)
        with self._host_lock:
            if self._public_host is not None:
                raise ValueError("代理已激活，不能更改公网域名。")
            self._public_host = public_host

    def process_request(self, request, client_address):
        if not self._workers.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._workers.release()

    def handle_error(self, request, client_address):
        # Never print request bodies, cookies, credentials or upstream errors.
        pass


def _route_allowed(method, path):
    if method == "GET":
        return (path in _STATIC or _ASSETS.fullmatch(path) is not None
                or path in {"/api/bootstrap", "/api/skills", "/api/releases/latest", "/downloads/latest.zip"}
                or re.fullmatch(rf"/api/conversations/{_CID}", path) is not None
                or re.fullmatch(rf"/media/{_CID}", path) is not None)
    if method == "POST":
        return (path in {"/api/conversations", "/api/providers/refresh", "/api/starters/generate", "/api/media"}
                or re.fullmatch(r"/api/skills/(?:norma|velina|sigrid|claret|roxy|lindverne|deepseek|gemini|gpt|dialyn|zhao|phoenix|banyue|promeia|vivian|hugo)(?:/undo)?", path) is not None
                or re.fullmatch(rf"/api/conversations/{_CID}/(?:messages|continue)", path) is not None
                or re.fullmatch(rf"/api/runs/{_CID}/stop", path) is not None)
    return method in {"PATCH", "DELETE"} and re.fullmatch(rf"/api/conversations/{_CID}", path) is not None


def _image_type(data):
    """Check transport signatures; the upstream validates the complete image."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _login_page(nonce, download=False):
    destination = json.dumps("/downloads/latest.zip" if download else "/")
    return f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>登录 · {APP_NAME}</title>
<style nonce="{nonce}">*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f3f6fa;color:#233449;font:16px system-ui,sans-serif;padding:24px}}main{{width:min(100%,390px);padding:34px;background:white;border:1px solid #dfe6ed;border-radius:20px;box-shadow:0 14px 44px #20364f10}}h1{{margin:0 0 12px;font-size:25px}}p{{color:#63758a;line-height:1.7}}label{{display:block;margin:24px 0 8px;font-weight:600}}input,button{{width:100%;font:inherit;padding:13px;border-radius:10px}}input{{border:1px solid #b9c8d7}}button{{border:0;margin-top:18px;background:#44739b;color:white;cursor:pointer}}button:disabled{{opacity:.6;cursor:wait}}#status{{min-height:26px;font-size:14px;color:#a33c4b}}</style>
<main><h1>欢迎来到{APP_NAME}</h1><p>输入访问密码，继续你的对话。</p><form id="login"><label for="password">访问密码</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="256" autofocus><button id="submit" type="submit">进入酒馆</button><p id="status" role="status" aria-live="polite"></p></form></main>
<script nonce="{nonce}">const form=document.querySelector('#login'),button=document.querySelector('#submit'),status=document.querySelector('#status');form.addEventListener('submit',async(event)=>{{event.preventDefault();button.disabled=true;status.textContent='正在验证…';try{{const response=await fetch('/api/auth/login',{{method:'POST',credentials:'same-origin',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{password:document.querySelector('#password').value}})}});if(response.ok){{document.querySelector('#password').value='';location.replace({destination});return;}}const data=await response.json();status.textContent=data.error||'登录失败，请重试。';}}catch{{status.textContent='暂时无法连接，请稍后重试。';}}finally{{button.disabled=false;}}}});</script></html>""".encode("utf-8")


def create_remote_server(port, upstream_port, public_host=None, password=None):
    """Bind loopback without starting; None host keeps every route locked.

    A launcher can first reserve the proxy's port, then create its tunnel, and
    finally call set_public_host() once the HTTPS hostname is known.
    """
    if public_host is not None:
        _validate_public_host(public_host)
    if type(port) is not int or not 0 <= port <= 65535 or type(upstream_port) is not int or not 1 <= upstream_port <= 65535:
        raise ValueError("代理端口或本机服务端口不正确。")
    auth = _Auth(password)
    upstream_host = f"127.0.0.1:{upstream_port}"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "WisdomTavern"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def handle(self):
            try:
                super().handle()
            except (ConnectionError, OSError, TimeoutError):
                pass

        def log_message(self, format, *args):
            pass

        def _send(self, status, body=b"", content_type="application/json; charset=utf-8", extras=None, *, cache_control="no-store"):
            self._send_headers(status, len(body), content_type, extras, cache_control=cache_control)
            if body:
                self.wfile.write(body)

        def _send_headers(self, status, length, content_type, extras=None, *, cache_control="no-store"):
            self.close_connection = True
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Connection", "close")
            self.send_header("Cache-Control", cache_control)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Strict-Transport-Security", "max-age=86400")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            for name, value in (extras or {}).items():
                self.send_header(name, value)
            self.end_headers()

        def _json(self, data, status=200, extras=None):
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), extras=extras)

        def _boundary(self):
            public_host = self.server.public_host
            if public_host is None:
                self._json({"error": "远程访问尚未准备好。"}, 503)
                return None
            public_origin = "https://" + public_host
            if self.headers.get_all("Host", []) != [public_host]:
                self._json({"error": "访问地址不正确。"}, 403)
                return None
            origins = self.headers.get_all("Origin", [])
            if len(origins) > 1 or (origins and origins != [public_origin]) or (self.command != "GET" and origins != [public_origin]):
                self._json({"error": "不允许跨站请求。"}, 403)
                return None
            if self.headers.get_all("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) > 1 or len(self.headers.get_all("Content-Type", [])) > 1:
                self._json({"error": "不支持此请求格式。"}, 400)
                return None
            length = self.headers.get("Content-Length", "0")
            if not re.fullmatch(r"[0-9]{1,10}", length) or (self.command == "GET" and int(length) != 0):
                self._json({"error": "请求大小或格式不正确。"}, 400)
                return None
            # BaseHTTPRequestHandler normalizes a leading // before dispatch.
            # Check the original target too, never just its normalized path.
            original_target = self.requestline.split()[1]
            if original_target != self.path or not self.path.startswith("/") or self.path.startswith("//") or len(self.path) > 2048 or any(ord(char) < 32 or ord(char) == 127 for char in self.path):
                self._json({"error": "请求路径不正确。"}, 400)
                return None
            try:
                parts = urlsplit(self.path)
            except ValueError:
                self._json({"error": "请求路径不正确。"}, 400)
                return None
            path = parts.path
            if parts.scheme or parts.netloc or parts.fragment or "%" in path or "\\" in self.path or "//" in path or any(piece in {".", ".."} for piece in path.split("/")):
                self._json({"error": "请求路径不正确。"}, 400)
                return None
            limit = MAX_UPLOAD if self.command == "POST" and path == "/api/media" else MAX_BODY
            if int(length) > limit:
                self._json({"error": "请求内容过大。"}, 413)
                return None
            # Tunnel hints can only restrict a request, never grant access.
            # Missing hints are useful for local health checks and tests. A
            # clear HTTP hint must not expose a form that submits a password.
            schemes = []
            forwarded_proto = self.headers.get_all("X-Forwarded-Proto", [])
            visitors = self.headers.get_all("CF-Visitor", [])
            try:
                if len(forwarded_proto) > 1 or len(visitors) > 1:
                    raise ValueError
                schemes.extend(forwarded_proto)
                if visitors:
                    visitor = json.loads(visitors[0])
                    if not isinstance(visitor, dict):
                        raise ValueError
                    schemes.append(visitor.get("scheme"))
                if any(scheme not in {"http", "https"} for scheme in schemes):
                    raise ValueError
            except (ValueError, TypeError):
                self._json({"error": "代理协议标记不正确。"}, 400)
                return None
            if "http" in schemes:
                if self.command == "GET":
                    self._send(308, extras={"Location": public_origin + self.path})
                else:
                    self._json({"error": "请通过 HTTPS 安全连接访问。"}, 403)
                return None
            return path

        def _body(self, limit=MAX_BODY, allow_empty=False, image=False):
            length = int(self.headers.get("Content-Length", "0"))
            if length > limit:
                self._json({"error": "请求内容过大。"}, 413)
                return None
            if not length and allow_empty:
                return b""
            content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if image and (content_type not in _IMAGE_TYPES or self.headers.get_all("Content-Encoding")):
                self._json({"error": "仅支持原始 PNG、JPEG 或 WebP 图片。"}, 415)
                return None
            if not length or (not image and content_type != "application/json"):
                self._json({"error": "图片内容不能为空。" if image else "请求须使用 JSON 格式。"}, 400)
                return None
            try:
                body = self.rfile.read(length)
            except (OSError, TimeoutError):
                self._json({"error": "读取请求超时。"}, 408)
                return None
            if len(body) != length:
                self._json({"error": "请求内容不完整。"}, 400)
                return None
            if image and _image_type(body) != content_type:
                self._json({"error": "图片内容与文件类型不一致。"}, 415)
                return None
            return body

        def _handle(self):
            path = self._boundary()
            if path is None:
                return
            if self.command == "GET" and path == "/api/health":
                return self._json({"ok": True})
            if self.command == "GET" and path == "/login":
                nonce = secrets.token_urlsafe(24)
                csp = f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
                return self._send(200, _login_page(nonce, self.path == "/login?download=1"), "text/html; charset=utf-8", {"Content-Security-Policy": csp})
            if self.command == "POST" and path == "/api/auth/login":
                body = self._body(4096)
                if body is None:
                    return
                try:
                    data = json.loads(body)
                    if not isinstance(data, dict) or set(data) != {"password"} or not isinstance(data["password"], str):
                        raise ValueError
                except (ValueError, UnicodeError):
                    return self._json({"error": "登录请求格式不正确。"}, 400)
                status, token = auth.login(data["password"])
                if status == 429:
                    return self._json({"error": "尝试过于频繁，请一分钟后再试。"}, 429, {"Retry-After": "60"})
                if status != 200:
                    return self._json({"error": "访问密码不正确。"}, 401)
                auth.logout(self.headers)  # Rotate a caller's existing session.
                return self._json({"ok": True}, extras={"Set-Cookie": f"{COOKIE_NAME}={token}; Path=/; Max-Age={SESSION_TTL}; HttpOnly; Secure; SameSite=Strict"})
            if not auth.authorized(self.headers):
                if path.startswith("/api/"):
                    return self._json({"error": "请先登录。"}, 401)
                return self._send(302, extras={"Location": "/login?download=1" if path == "/downloads/latest.zip" else "/login"})
            if self.command == "POST" and path == "/api/auth/logout":
                body = self._body(4096, allow_empty=True)
                if body is None:
                    return
                auth.logout(self.headers)
                return self._json({"ok": True}, extras={"Set-Cookie": f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict"})
            if path == "/api/events":
                return self._json({"error": "远程访问使用轮询，请刷新页面。", "eventTransport": "poll"}, 409)
            if not _route_allowed(self.command, path):
                return self._json({"error": "接口或文件不存在。"}, 404)
            body = b""
            upload = self.command == "POST" and path == "/api/media"
            if self.command != "GET":
                body = self._body(limit=MAX_UPLOAD if upload else MAX_BODY, allow_empty=self.command == "DELETE", image=upload)
                if body is None:
                    return
            content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower() if upload else "application/json"
            self._forward(path, body, content_type)

        def _forward(self, path, body, request_type):
            connection = http.client.HTTPConnection("127.0.0.1", upstream_port, timeout=90)
            # Rebuild headers. Only the validated opaque visitor identity reaches
            # the app; session cookies and upstream credentials never do.
            headers = {"Host": upstream_host, "Connection": "close", "Accept-Encoding": "identity"}
            cookie_headers = self.headers.get_all('Cookie', [])
            visitor = cookie_identity(cookie_headers[0]) if len(cookie_headers) == 1 else None
            if visitor:
                headers['Cookie'] = f'{VISITOR_COOKIE}={visitor}'
            if self.command != "GET":
                headers.update({"Origin": "http://" + upstream_host, "Content-Type": request_type})
            try:
                connection.request(self.command, self.path, body=body or None, headers=headers)
                response = connection.getresponse()
                if response.status < 200:
                    raise ValueError
                extras = {}
                visitors = [identity for value in response.headers.get_all('Set-Cookie', [])
                            if (identity := cookie_identity(value))]
                if len(visitors) == 1:
                    extras['Set-Cookie'] = visitor_cookie(visitors[0], secure=True)
                if path == "/downloads/latest.zip" and response.status == 200:
                    return self._forward_download(response, extras)
                advertised = response.getheader("Content-Length")
                if advertised and (not advertised.isdigit() or int(advertised) > MAX_RESPONSE):
                    raise ValueError
                payload = response.read(MAX_RESPONSE + 1)
                if len(payload) > MAX_RESPONSE:
                    raise ValueError
                content_type = response.getheader("Content-Type", "application/octet-stream")
                private_image = path.startswith("/media/") and response.status == 200
                if private_image:
                    content_type = content_type.split(";")[0].strip().lower()
                    if content_type not in _IMAGE_TYPES or _image_type(payload) != content_type:
                        raise ValueError
                if path in {"/api/bootstrap", "/api/providers/refresh"} and response.status == 200:
                    data = json.loads(payload)
                    if not isinstance(data, dict):
                        raise ValueError
                    if path == '/api/bootstrap':
                        data["eventTransport"] = "poll"
                    capabilities = data.get('capabilities')
                    capabilities = dict(capabilities) if isinstance(capabilities, dict) else {}
                    capabilities['localConnection'] = {'available': False}
                    data['capabilities'] = capabilities
                    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
                    content_type = "application/json; charset=utf-8"
                csp = response.getheader("Content-Security-Policy")
                if csp:
                    extras['Content-Security-Policy'] = csp
                self._send(response.status, payload, content_type, extras,
                           cache_control="private, no-store" if private_image else "no-store")
            except (OSError, http.client.HTTPException, ValueError, UnicodeError):
                self._json({"error": "本机酒馆暂时不可用，请稍后重试。"}, 502)
            finally:
                connection.close()

        def _forward_download(self, response, extras=None):
            # Only this authenticated, fixed route can exceed MAX_RESPONSE.
            # Validate framing before streaming; never buffer a whole package.
            lengths = response.headers.get_all("Content-Length", [])
            disposition = response.getheader("Content-Disposition", "")
            if (len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0])
                    or not 4 <= int(lengths[0]) <= MAX_RELEASE_BYTES
                    or response.getheader("Transfer-Encoding")
                    or response.getheader("Content-Encoding")
                    or response.getheader("Content-Type") != "application/zip"
                    or not re.fullmatch(r'attachment; filename="' + RELEASE_FILENAME + r'"', disposition)):
                raise ValueError
            size = int(lengths[0])
            first = response.read(min(65536, size))
            if not first.startswith(b"PK\x03\x04") or len(first) != min(65536, size):
                raise ValueError
            self._send_headers(200, size, "application/zip", {**(extras or {}), "Content-Disposition": disposition},
                               cache_control="private, no-store")
            try:
                self.wfile.write(first)
                remaining = size - len(first)
                while remaining:
                    chunk = response.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise OSError("Incomplete package")
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except (OSError, http.client.HTTPException):
                # Headers already went out. Close the stream so the browser
                # detects a truncated download; don't append an error to ZIP.
                self.close_connection = True

        def do_GET(self):
            self._handle()

        def do_POST(self):
            self._handle()

        def do_PATCH(self):
            self._handle()

        def do_DELETE(self):
            self._handle()

        def _unsupported(self):
            if self._boundary() is None:
                return
            self._json({"error": "不支持此请求方法。"}, 405, {"Allow": "GET, POST, PATCH, DELETE"})

        do_CONNECT = do_HEAD = do_OPTIONS = do_PUT = do_TRACE = _unsupported

        def handle_expect_100(self):
            self._json({"error": "不支持此请求格式。"}, 417)
            return False

    server = RemoteServer(("127.0.0.1", port), Handler)
    server.auth = auth
    server.upstream_port = upstream_port
    if public_host is not None:
        server.set_public_host(public_host)
    return server


def main():
    parser = argparse.ArgumentParser(description=f"启动{APP_NAME}的本机认证代理，供 HTTPS 隧道连接。")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--upstream-port", type=int, default=8765)
    parser.add_argument("--public-host", required=True)
    args = parser.parse_args()
    password = os.environ.get("TAVERN_REMOTE_PASSWORD") or getpass.getpass("远程访问密码：")
    server = create_remote_server(args.port, args.upstream_port, args.public_host, password)
    del password
    print(f"本机认证代理已监听 127.0.0.1:{server.server_port}。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
