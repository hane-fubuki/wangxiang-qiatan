"""妄想洽谈中 — loopback HTTP service with native Codex image understanding."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import queue
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen

from backend import APP_NAME
from backend.engine import Engine
from backend.providers import GatewayError, ModelGateway
from backend.rooms import public_rooms
from backend.starters import StarterGenerator
from backend.store import Store
from backend.identity import identity_changed
from backend.skills import SkillStore, SkillConflict, IDS as SKILL_IDS, editable_ids, skill_room
from backend.media import MediaStore, MAX_UPLOAD, MIMES
from backend.codex_media import CodexMedia
from backend.codex_research import CodexResearch
from backend.releases import Releases, ReleaseUnavailable
from backend.local_connection import LocalConnection
from backend.visitors import cookie_identity, new_identity, visitor_cookie, can_access, public_conversation, MediaAccess
from backend.web_knowledge import KnowledgeStore
from backend.wiki_research import PublicResearch
from backend.local_access import APP_PORT, LEGACY_PORT, canonical_port, create_local_redirect

ROOT = Path(__file__).resolve().parent


def user_profile():
    avatar = ROOT / "web/assets/user-avatar.png"
    try:
        # A new URL makes browsers replace the already-decoded previous avatar.
        version = hashlib.sha256(avatar.read_bytes()).hexdigest()[:16] if avatar.is_file() else None
    except OSError:
        version = None
    return {"name": "你", "avatar": f"/assets/user-avatar.png?v={version}" if version else None}


class Events:
    def __init__(self, store):
        self.lock = threading.Lock()
        self.listeners = {}
        self.store = store
        # Retain deleted owners too, so late worker events cannot become public.
        self.owners = {item['id']: item.get('ownerId') for item in store.list()}

    def emit(self, event, data):
        with self.lock:
            conversation = data.get('conversation') if isinstance(data, dict) else None
            cid = conversation.get('id') if conversation else data.get('conversationId') if isinstance(data, dict) else None
            if conversation:
                self.owners[cid] = conversation.get('ownerId')
                data = {**data, 'conversation': public_conversation(conversation)}
            if cid and cid not in self.owners:
                try:
                    self.owners[cid] = self.store.get(cid).get('ownerId')
                except KeyError:
                    return
            owner = self.owners.get(cid)
            payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
            for listener, visitor in tuple(self.listeners.items()):
                if owner and owner != visitor:
                    continue
                try:
                    listener.put_nowait(payload)
                except queue.Full:
                    # Force a browser resync instead of silently dropping chat events.
                    try:
                        listener.get_nowait()
                        listener.put_nowait(b"event: resync\ndata: {}\n\n")
                    except queue.Empty:
                        pass


def create_server(port=APP_PORT, data_dir=None, gateway=None, codex_media=None, research=None, releases_dir=None):
    store = Store(data_dir or ROOT / ".tavern")
    events = Events(store)
    gateway = gateway or ModelGateway(connection_path=store.directory / "model-connection.bin")
    local_connection = getattr(gateway, "local_connection", None) or LocalConnection(store.directory / "model-connection.bin")
    media = MediaStore(store.directory / "media")
    media_access = MediaAccess(store.directory / "media-access.json")
    knowledge = KnowledgeStore(store.directory / "web-knowledge")
    skills = SkillStore(store.directory / "skills")
    if codex_media is None and isinstance(gateway, ModelGateway):
        codex_media = CodexMedia(gateway._settings.codex, store.directory / "generated")
    if research is None and isinstance(gateway, ModelGateway):
        research = PublicResearch(gateway._settings.codex)
    engine = Engine(store, gateway, events.emit, skills=skills, media=media, codex_media=codex_media,
                    research=research, knowledge=knowledge, media_access=media_access)
    starters = StarterGenerator(gateway)
    releases = Releases(releases_dir if releases_dir is not None else ROOT / ".tavern" / "releases")

    def model_options():
        if hasattr(gateway, "model_options"):
            return gateway.model_options()
        return [{"providerId": item["id"], "model": item["model"], "name": item.get("name", item["id"]),
                 "configured": item.get("configured", False)} for item in gateway.status() if item.get("model")]

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def handle(self):
            try:
                super().handle()
            except (ConnectionError, TimeoutError):
                # Browsers routinely close keep-alive sockets on reload or exit.
                pass

        def log_message(self, format, *args):
            pass

        def _visitor(self):
            values = self.headers.get_all("Cookie", [])
            supplied = cookie_identity(values[0]) if len(values) == 1 else None
            self.visitor = supplied or new_identity()
            self.visitor_new = supplied is None

        def end_headers(self):
            if getattr(self, "visitor_new", False):
                self.send_header("Set-Cookie", visitor_cookie(self.visitor))
                self.visitor_new = False
            super().end_headers()

        def _conversation(self, cid):
            conversation = store.get(cid)
            if not can_access(conversation, self.visitor):
                raise KeyError(cid)
            return conversation

        def _local_connection_request(self, mutation=False):
            # Compatible-API credentials may be edited only by same-origin local UI.
            allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            origins = self.headers.get_all("Origin", [])
            if len(origins) > 1 or origins and origins[0] not in allowed or mutation and not origins:
                self._json({"error": "请从本机酒馆页面管理模型连接"}, 403)
                return False
            return True

        def _json(self, data, status=200):
            if isinstance(data, dict):
                if 'ownerId' in data:
                    data = public_conversation(data)
                elif isinstance(data.get('conversation'), dict):
                    data = {**data, 'conversation': public_conversation(data['conversation'])}
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _local(self):
            self.visitor_new = False
            expected_port = self.server.server_port
            allowed = {f"127.0.0.1:{expected_port}", f"localhost:{expected_port}"}
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1 or hosts[0] not in allowed:
                self._json({"error": "仅允许本机访问"}, 403)
                self.close_connection = True
                return False
            origins = self.headers.get_all("Origin", [])
            if len(origins) > 1 or origins and origins[0] not in {f"http://{host}" for host in allowed}:
                self._json({"error": "不允许跨站请求"}, 403)
                self.close_connection = True
                return False
            return True

        def _body(self):
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("请求须使用 JSON 格式")
            if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                raise ValueError("不支持此传输格式")
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 131072:
                raise ValueError("请求为空或过大")
            self.connection.settimeout(10)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("请求格式不正确")
            return data

        def _upload(self):
            mime = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if mime not in MIMES:
                raise ValueError("请选择 PNG、JPEG 或 WebP 图片")
            if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                raise ValueError("不支持此传输格式")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_UPLOAD:
                raise ValueError("单张图片最多 8 MiB")
            self.connection.settimeout(20)
            data = self.rfile.read(length)
            if len(data) != length:
                raise ValueError("图片上传不完整")
            return media.add(data, mime)

        def do_GET(self):
            if not self._local():
                return
            self._visitor()
            path = urlparse(self.path).path
            try:
                if path == "/api/health":
                    return self._json({"ok": True, "app": APP_NAME, "version": "1.0.0"})
                if path in {"/downloads/latest.zip", "/api/releases/latest"}:
                    try:
                        info, package = releases.open_latest()
                    except ReleaseUnavailable as exc:
                        return self._json({"error": str(exc)}, 404)
                    with package:
                        if path == "/api/releases/latest":
                            return self._json(info)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/zip")
                        self.send_header("Content-Length", str(info["size"]))
                        self.send_header("Content-Disposition", f'attachment; filename="{info["filename"]}"')
                        self.send_header("Cache-Control", "private, no-store")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.end_headers()
                        try:
                            while chunk := package.read(1024 * 1024):
                                self.wfile.write(chunk)
                        except (OSError, ConnectionError):
                            self.close_connection = True
                        return
                if path == "/api/bootstrap":
                    conversations = [item for item in store.list() if can_access(item, self.visitor)]
                    visible = {item['id'] for item in conversations}
                    return self._json({"providers": gateway.status(), "rooms": public_rooms(), "conversations": [public_conversation(item) for item in conversations],
                                       "activeRuns": {cid: run for cid, run in engine.snapshot().items() if cid in visible},
                                       "userProfile": user_profile(), "runStates": {cid: state for cid, state in engine.state_snapshot().items() if cid in visible}, "modelOptions": model_options(),
                                       "roomProviders": {room["id"]: engine.room_status(room["id"]) for room in public_rooms()},
                                       "capabilities": {"localConnection": {"available": True}, "webSearch": engine.research.status() if engine.research else {"configured": False},
                                                        "imageGeneration": engine.codex_media.status() if engine.codex_media else {"configured": False, "detail": "请在本机 Codex 登录 ChatGPT 后刷新模型连接"}}})
                if path == "/api/local-connection":
                    if self._local_connection_request():
                        return self._json(local_connection.metadata())
                    return
                if path == "/api/skills":
                    return self._json({"skills": skills.list(parse_qs(urlparse(self.path).query).get("roomId", ["zzz-trio"])[0])})
                match = re.fullmatch(r"/media/([a-f0-9]{32})", path)
                if match:
                    if not media_access.allowed(match[1], self.visitor):
                        raise KeyError(match[1])
                    info, payload = media.read(match[1])
                    self.send_response(200)
                    self.send_header("Content-Type", info["mime"])
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("Cache-Control", "private, no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if path == "/api/events":
                    return self._events()
                match = re.fullmatch(r"/api/conversations/([a-f0-9]{32})", path)
                if match:
                    return self._json(self._conversation(match[1]))
                if path.startswith("/api/"):
                    return self._json({"error": "接口不存在"}, 404)
                # Explicit asset allowlist prevents serving local history, config, or source.
                filename = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js",
                            "/styles.css": "styles.css", "/tea-theme.css": "tea-theme.css", "/studio-theme.css": "studio-theme.css", "/yunkui-theme.css": "yunkui-theme.css", "/obol-theme.css": "obol-theme.css", "/favicon.svg": "favicon.svg",
                            "/roscaelifer-theme.css": "roscaelifer-theme.css", "/roscaelifer-icons.js": "roscaelifer-icons.js",
                            "/outer-ring-theme.css": "outer-ring-theme.css", "/outer-ring-icons.js": "outer-ring-icons.js",
                            "/mockingbird-theme.css": "mockingbird-theme.css", "/mockingbird-icons.js": "mockingbird-icons.js",
                            "/assets/user-avatar.png": "assets/user-avatar.png",
                            "/assets/tea-party-reference.jpg": "assets/tea-party-reference.jpg"}.get(path)
                if re.fullmatch(r"/assets/(deepseek|gemini|gpt|grok)-(stand|avatar)\.png", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/protagonist-(lumine|belle)-(stand|avatar)\.png", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/(deepseek|gemini|gpt|grok)-(original\.jpg|avatar-reference\.png)", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/zzz-(sunna|nangong-yu|aria)-(stand|avatar)\.png", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/roscaelifer-(norma|velina|sigrid|claret|roxy|lindverne)-(stand|avatar)\.png", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/outer-ring-(burnice|caesar|lucy|lighter|pulchra|piper)-(stand|avatar)\.png", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/mockingbird-(vivian|hugo)-(stand|avatar)\.png", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/obol-(seed|magus|orphie|trigger|soldier11|silver-anby)-(stand|avatar)\.png", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/yunkui-(yixuan|ye-shunguang|pan-yinhu|ju-fufu)-(stand|avatar)\.png", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/krampus-(dialyn|zhao|phoenix|banyue|promeia)-(stand|avatar)\.png", path):
                    filename = path.lstrip("/")
                if re.fullmatch(r"/assets/wangsheng-(?:(?:gemini|deepseek|gpt)-(?:stand|avatar)\.png|(?:room|paimon|xiangling|xiao|zibai)\.png|(?:gemini|deepseek|gpt|paimon|xiangling|xiao|zibai)\.svg)", path):
                    filename = path.lstrip("/")
                if not filename or not (ROOT / "web" / filename).is_file():
                    return self._json({"error": "文件不存在"}, 404)
                payload = (ROOT / "web" / filename).read_bytes()
                self.send_response(200)
                mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or filename.endswith(".js") else ""))
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
                self.end_headers()
                self.wfile.write(payload)
            except KeyError:
                self._json({"error": "会话不存在"}, 404)
            except (ValueError, OSError):
                self._json({"error": "图片不存在或无法读取"}, 404)
            except (ConnectionError, BrokenPipeError):
                pass

        def _events(self):
            listener = queue.Queue(maxsize=256)
            with events.lock:
                events.listeners[listener] = self.visitor
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                self.wfile.write(b"retry: 1500\n\n")
                self.wfile.flush()
                while True:
                    try:
                        payload = listener.get(timeout=15)
                    except queue.Empty:
                        payload = b": heartbeat\n\n"
                    self.wfile.write(payload)
                    self.wfile.flush()
            except (ConnectionError, OSError):
                pass
            finally:
                with events.lock:
                    events.listeners.pop(listener, None)

        def do_POST(self):
            self._mutate("POST")

        def do_PATCH(self):
            self._mutate("PATCH")

        def do_DELETE(self):
            self._mutate("DELETE")

        def _mutate(self, method):
            if not self._local():
                return
            self._visitor()
            path = urlparse(self.path).path
            try:
                if method == "POST" and path == "/api/media":
                    uploaded = self._upload()
                    media_access.claim([uploaded['id']], self.visitor)
                    return self._json(uploaded, 201)
                data = self._body() if method != "DELETE" else {}
                if method == "POST" and path in {"/api/local-connection/save", "/api/local-connection/test", "/api/local-connection/clear"}:
                    if not self._local_connection_request(mutation=True):
                        return
                    action = path.rsplit('/', 1)[1]
                    if action == 'test':
                        return self._json(local_connection.test(data))
                    if action == 'save':
                        result = local_connection.save(data)
                    else:
                        local_connection.clear()
                        result = local_connection.metadata()
                    if hasattr(gateway, 'refresh'):
                        gateway.refresh()
                    events.emit('providers', gateway.status())
                    return self._json(result)
                match = re.fullmatch(r"/api/skills/([a-z0-9-]+)(/undo)?", path)
                if method == "POST" and match:
                    if match[1] not in SKILL_IDS:
                        raise ValueError("未知的角色设定。")
                    requested_room = data.get("roomId", skill_room(match[1]))
                    if match[1] not in editable_ids(requested_room):
                        raise ValueError("该角色不属于当前房间的可编辑设定。")
                    if type(data.get("expectedVersion")) is not int:
                        raise ValueError("请先载入角色设定版本")
                    item = skills.undo(match[1], data["expectedVersion"]) if match[2] else skills.update(match[1], data.get("content"), data["expectedVersion"])
                    events.emit("skills", {"id": item["id"], "version": item["version"]})
                    return self._json(item)
                if method == "POST" and path == "/api/starters/generate":
                    return self._json(starters.generate(data.get("roomId", "standard"), data.get("starterId")))
                if method == "POST" and path == "/api/conversations":
                    room_id = data.get("roomId", "standard")
                    conversation = store.create(room_id=room_id, owner_id=self.visitor if room_id == "wangsheng-trio" else None)
                    events.emit("conversation", {"conversation": conversation})
                    return self._json(conversation, 201)
                if method == "POST" and path == "/api/providers/refresh":
                    if hasattr(gateway, "refresh"):
                        gateway.refresh()
                    if isinstance(gateway, ModelGateway):
                        engine.codex_media = CodexMedia(gateway._settings.codex, store.directory / "generated")
                        engine.research = PublicResearch(gateway._settings.codex)
                    providers = gateway.status()
                    events.emit("providers", providers)
                    return self._json({"providers": providers, "modelOptions": model_options(), "roomProviders": {room["id"]: engine.room_status(room["id"]) for room in public_rooms()},
                                       "capabilities": {"localConnection": {"available": True}, "webSearch": engine.research.status() if engine.research else {"configured": False},
                                                        "imageGeneration": engine.codex_media.status() if engine.codex_media else {"configured": False, "detail": "请在本机 Codex 登录 ChatGPT"}}})
                match = re.fullmatch(r"/api/conversations/([a-f0-9]{32})(?:/(messages|continue))?", path)
                if match:
                    cid, action = match.groups()
                    current = self._conversation(cid)
                    if method == "POST" and action == "messages":
                        if not isinstance(data.get("content"), str):
                            raise ValueError("请输入消息")
                        attachments = data.get('attachments', [])
                        if not isinstance(attachments, list) or any(not isinstance(item, str) for item in attachments):
                            raise ValueError('图片编号无效')
                        if any(not media_access.allowed(item, self.visitor) for item in attachments):
                            raise KeyError(cid)
                        result = engine.start(cid, data["content"], data.get("settings"), attachments, data.get("intent", "auto"))
                        if attachments:
                            media_access.claim(attachments, current.get('ownerId'))
                        return self._json(result)
                    if method == "POST" and action == "continue":
                        return self._json(engine.start(cid, settings=data.get("settings")))
                    if method == "PATCH" and action is None:
                        with engine.lock:
                            current = self._conversation(cid)
                            validated = store.validate_update(cid, data)
                            if "settings" in validated:
                                selected = validated["settings"]
                                engine.room_status(current["roomId"], selected["models"])
                                if identity_changed(current, selected):
                                    engine.stop_conversation(cid)
                            item = store.update(cid, validated)
                        events.emit("conversation", {"conversation": item})
                        return self._json(item)
                    if method == "DELETE" and action is None:
                        with engine.lock:
                            engine.stop_conversation(cid)
                            store.delete(cid)
                        events.emit("deleted", {"conversationId": cid})
                        return self._json({"ok": True})
                match = re.fullmatch(r"/api/runs/([a-f0-9]{32})/stop", path)
                if method == "POST" and match:
                    with engine.lock:
                        cid = next((cid for cid, run_id in engine.snapshot().items() if run_id == match[1]), None)
                        if cid is None:
                            raise KeyError(match[1])
                        self._conversation(cid)
                        engine.stop(match[1])
                    return self._json({"ok": True})
                self._json({"error": "接口不存在"}, 404)
            except KeyError:
                self._json({"error": "会话不存在"}, 404)
            except GatewayError as error:
                self._json({"error": str(error)}, 503)
            except SkillConflict as error:
                self._json({"error": str(error)}, 409)
            except (ValueError, UnicodeError):
                self.close_connection = True
                # Do not echo arbitrary malformed request contents.
                import sys
                error = sys.exception()
                message = str(error) if type(error) is ValueError else "请求格式不正确"
                self._json({"error": message}, 400)
            except (ConnectionError, BrokenPipeError):
                pass
            except Exception:
                self._json({"error": "操作失败，请检查本机服务状态"}, 500)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.engine, server.store, server.starters, server.media, server.skills = engine, store, starters, media, skills
    server.events, server.media_access, server.local_connection, server.knowledge = events, media_access, local_connection, knowledge
    return server


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} · 多模型自由对话")
    parser.add_argument("--port", type=int, default=APP_PORT)
    parser.add_argument("--open", action="store_true", help="在浏览器打开")
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()
    args.port = canonical_port(args.port)
    address = f"http://127.0.0.1:{args.port}"
    server = redirect = None
    redirect_thread = None
    try:
        server = create_server(args.port, args.data_dir)
        if args.port == APP_PORT:
            redirect = create_local_redirect()
    except OSError as exc:
        if server is not None:
            server.server_close()
        if args.open:
            try:
                with urlopen(address + "/api/health", timeout=1) as response:
                    existing = json.load(response)
                if isinstance(existing, dict) and existing.get("ok") and existing.get("app") == APP_NAME:
                    webbrowser.open(address)
                    print(f"{APP_NAME}已在运行，已打开：{address}")
                    return
            except (OSError, ValueError):
                pass
        raise SystemExit(f"无法启动服务（端口可能被占用）。请检查 {args.port} 和旧入口 {LEGACY_PORT} 是否已有独立实例：{exc}")
    address = f"http://127.0.0.1:{server.server_port}"
    if redirect is not None:
        redirect_thread = threading.Thread(target=redirect.serve_forever, daemon=True)
        redirect_thread.start()
    print(f"{APP_NAME}已启动：{address}\n按 Ctrl+C 停止服务。", flush=True)
    if redirect is not None:
        print(f"旧入口 http://127.0.0.1:{LEGACY_PORT}/ 自动转到同一服务。", flush=True)
    if args.open:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if redirect is not None:
            redirect.shutdown()
            redirect.server_close()
            redirect_thread.join(timeout=3)
        server.engine.stop_all()
        server.starters.cancel_all()
        server.server_close()


if __name__ == "__main__":
    main()
