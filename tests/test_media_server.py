"""Media and character settings across real HTTP, with no external model calls."""
import http.client
import json
from pathlib import Path
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zlib

from app import create_server
from backend.media import MAX_UPLOAD
from backend.rooms import public_rooms


def png(rgb=b"\x00\x80\xff"):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0" + rgb)) + chunk(b"IEND", b""))


UPLOADED_PNG = png()
GENERATED_PNG = png(b"\xff\x40\x00")


class FakeGateway:
    def __init__(self):
        self.calls = []
        self.configured = True

    def status(self):
        return [{"id": slot, "name": name, "configured": self.configured, "model": "fake-" + slot}
                for slot, name in (("deepseek", "DeepSeek"), ("gemini", "Gemini"), ("gpt", "GPT"))]

    def room_status(self, room_id):
        result = self.status()
        if room_id == "zzz-trio":
            result[0].update(name="Gemini", model="gemini-4-argon", source="gemini")
        return result

    def respond_for(self, room_id, provider, prompt, cancel):
        self.calls.append((room_id, provider, prompt))
        return json.dumps({"speak": True, "to": "user", "content": "假模型已收到。"})


class FakeMedia:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.configured = True
        self.analyzed = []
        self.generated = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()

    def status(self):
        return {"configured": self.configured, "source": "codex", "model": "fake-codex",
                "detail": "假图片服务可用" if self.configured else "假图片服务未登录"}

    def analyze(self, image_paths, prompt, cancel):
        self.analyzed.append(([Path(path).read_bytes() for path in image_paths], prompt))
        return "图片是一个蓝色像素。"

    def generate(self, prompt, image_paths, cancel):
        self.generated.append((prompt, [Path(path).read_bytes() for path in image_paths]))
        self.started.set()
        if not self.release.wait(timeout=4):
            raise RuntimeError("Test generation gate was not released")
        if cancel.is_set():
            return []
        output = self.directory / "fake-generated.png"
        output.write_bytes(GENERATED_PNG)
        return [output]


class MediaServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.start_server()
        self.addCleanup(self.stop_server)

    def start_server(self):
        self.gateway = FakeGateway()
        self.fake_media = FakeMedia(self.temp.name)
        self.server = create_server(port=0, data_dir=self.temp.name,
                                    gateway=self.gateway, codex_media=self.fake_media)
        # HTTP/media tests keep cancellation checks; reply timing has dedicated tests.
        engine = self.server.engine
        reply_clock = patch.object(engine, "_wait_for_reply", side_effect=lambda run, provider: engine._current(run))
        reply_clock.start()
        self.addCleanup(reply_clock.stop)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop_server(self):
        self.server.engine.stop_all()
        self.fake_media.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, path, payload=None, *, raw=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        body = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        request_headers = {"Content-Type": "application/json"} if body is not None else {}
        if getattr(self, 'visitor_cookie', None):
            request_headers['Cookie'] = self.visitor_cookie
        request_headers.update(headers or {})
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            data = response.read()
            visitor_cookie = response.getheader('Set-Cookie')
            if visitor_cookie and visitor_cookie.startswith('tavern_visitor='):
                self.visitor_cookie = visitor_cookie.split(';', 1)[0]
            if response.getheader("Content-Type", "").startswith("application/json"):
                data = json.loads(data)
            return response.status, data, dict(response.getheaders())
        finally:
            connection.close()

    def upload(self):
        status, info, _ = self.request("POST", "/api/media", raw=UPLOADED_PNG,
                                       headers={"Content-Type": "image/png"})
        self.assertEqual(status, 201)
        return info

    def create(self, room="standard"):
        status, conversation, _ = self.request("POST", "/api/conversations", {"roomId": room})
        self.assertEqual(status, 201)
        return conversation["id"]

    def skill(self, identifier="deepseek"):
        status, data, _ = self.request("GET", "/api/skills")
        self.assertEqual(status, 200)
        return next(item for item in data["skills"] if item["id"] == identifier)

    def wait_finished(self, cid):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            status, data, _ = self.request("GET", "/api/bootstrap")
            self.assertEqual(status, 200)
            if cid not in data["activeRuns"]:
                status, conversation, _ = self.request("GET", "/api/conversations/" + cid)
                self.assertEqual(status, 200)
                self.assertFalse([m for m in conversation["messages"] if m.get("kind") == "error"])
                return conversation
            threading.Event().wait(0.01)
        self.fail("Fake model run did not complete")

    def assert_private_png(self, url, expected):
        status, body, headers = self.request("GET", url)
        self.assertEqual(status, 200)
        self.assertEqual(body, expected)
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertEqual(int(headers["Content-Length"]), len(expected))
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_upload_roundtrip_returns_exact_private_image(self):
        info = self.upload()
        self.assertRegex(info["id"], r"^[a-f0-9]{32}$")
        self.assertEqual(info, {"id": info["id"], "url": "/media/" + info["id"],
                                "mime": "image/png", "width": 1, "height": 1})
        self.assert_private_png(info["url"], UPLOADED_PNG)
        self.assertEqual(self.gateway.calls, [])
        self.assertEqual(self.fake_media.analyzed, [])
        self.assertEqual(self.fake_media.generated, [])

    def test_upload_rejects_invalid_mime_bytes_and_declared_body_limits(self):
        cases = [
            (UPLOADED_PNG, {"Content-Type": mime})
            for mime in ("image/gif", "text/plain", "application/json", "image/jpeg")
        ] + [(b"not an image", {"Content-Type": "image/png"}),
             (b"", {"Content-Type": "image/png"}),
             (b"", {"Content-Type": "image/png", "Content-Length": str(MAX_UPLOAD + 1)}),
             (b"", {"Content-Type": "image/png", "Content-Length": "-1"}),
             (UPLOADED_PNG, {"Content-Type": "image/png", "Transfer-Encoding": "chunked"})]
        for body, headers in cases:
            with self.subTest(headers=headers, length=len(body)):
                status, data, _ = self.request("POST", "/api/media", raw=body, headers=headers)
                self.assertEqual(status, 400)
                self.assertIn("error", data)
        self.assertEqual(list((Path(self.temp.name) / "media").iterdir()), [])

    def test_media_paths_do_not_expose_files_or_allow_traversal(self):
        info = self.upload()
        for path in ("/media/", "/media/" + "0" * 32, info["url"] + ".png",
                     info["url"] + "/../skills", "/media/../conversations.json",
                     "/media/%2e%2e/conversations.json", "/media/%2f" + info["id"],
                     "/.tavern/media/" + info["id"], "/backend/media.py", "/api/media"):
            with self.subTest(path=path):
                status, data, _ = self.request("GET", path)
                self.assertEqual(status, 404)
                self.assertIn("error", data)

    def test_bootstrap_and_refresh_expose_room_provider_and_image_capability_contract(self):
        for method, path, body in (("GET", "/api/bootstrap", None),
                                   ("POST", "/api/providers/refresh", {})):
            with self.subTest(path=path):
                status, data, _ = self.request(method, path, body)
                self.assertEqual(status, 200)
                self.assertEqual(set(data["roomProviders"]), {room["id"] for room in public_rooms()})
                standard = {item["id"]: item for item in data["roomProviders"]["standard"]}
                roleplay = {item["id"]: item for item in data["roomProviders"]["zzz-trio"]}
                self.assertEqual(set(standard), {"deepseek", "gemini", "gpt"})
                self.assertEqual(set(roleplay), set(standard))
                self.assertEqual(standard["deepseek"]["name"], "DeepSeek")
                self.assertEqual(roleplay["deepseek"]["model"], "gemini-4-argon")
                self.assertEqual(data["capabilities"]["imageGeneration"], self.fake_media.status())
        self.fake_media.configured = False
        capability = self.request("GET", "/api/bootstrap")[1]["capabilities"]["imageGeneration"]
        self.assertFalse(capability["configured"])
        self.assertIn("未登录", capability["detail"])

    def test_skill_update_conflict_and_undo_keep_base_unchanged(self):
        status, data, _ = self.request("GET", "/api/skills")
        self.assertEqual(status, 200)
        self.assertEqual({item["id"] for item in data["skills"]}, {"deepseek", "gemini", "gpt", "belle"})
        initial = self.skill()
        self.assertEqual(initial["version"], 0)
        self.assertEqual(initial["content"], "")
        self.assertTrue(initial["base"])
        self.assertEqual(initial["history"], [])
        self.assertFalse(initial["canUndo"])
        status, saved, _ = self.request("POST", "/api/skills/deepseek",
                                        {"content": "回答时少用感叹号。", "expectedVersion": 0})
        self.assertEqual(status, 200)
        self.assertEqual(saved["version"], 1)
        self.assertEqual(saved["base"], initial["base"])
        self.assertEqual(saved["content"], "回答时少用感叹号。")
        self.assertEqual(saved["history"][0]["version"], 1)
        self.assertTrue(saved["updatedAt"])
        self.assertTrue(saved["canUndo"])
        for suffix in ("", "/undo"):
            status, error, _ = self.request("POST", "/api/skills/deepseek" + suffix,
                                            {"content": "stale overwrite", "expectedVersion": 0})
            self.assertEqual(status, 409)
            self.assertIn("error", error)
            self.assertEqual(self.skill(), saved)
        status, undone, _ = self.request("POST", "/api/skills/deepseek/undo", {"expectedVersion": 1})
        self.assertEqual(status, 200)
        self.assertEqual(undone["content"], "")
        self.assertEqual(undone["version"], 2)
        self.assertEqual(undone["base"], initial["base"])
        self.assertFalse(undone["canUndo"])
        self.assertEqual(self.skill(), undone)

    def test_skill_write_requires_valid_version_and_content(self):
        initial = self.skill()
        for payload in ({"content": "x"}, {"content": "x", "expectedVersion": True},
                        {"content": "x", "expectedVersion": "0"},
                        {"content": None, "expectedVersion": 0},
                        {"content": "x" * 6001, "expectedVersion": 0}):
            with self.subTest(payload_type={key: type(value).__name__ for key, value in payload.items()}):
                self.assertEqual(self.request("POST", "/api/skills/deepseek", payload)[0], 400)
                self.assertEqual(self.skill(), initial)

    def test_chat_skill_command_has_no_run_and_persists_into_future_model_context(self):
        cid = self.create("zzz-trio")
        path = f"/api/conversations/{cid}/messages"
        supplement = "每次回答先说测试暗号薄荷，然后简短回应。"
        status, data, _ = self.request("POST", path, {"content": "/设定 南宫羽 " + supplement})
        self.assertEqual(status, 200)
        self.assertNotIn("runId", data)
        self.assertEqual(data["command"], {"type": "skill", "id": "deepseek", "version": 1})
        self.assertEqual([m["role"] for m in data["conversation"]["messages"]], ["user", "system"])
        self.assertEqual(self.gateway.calls, [])
        self.assertEqual(self.request("GET", "/api/bootstrap")[1]["activeRuns"], {})
        self.stop_server()
        self.start_server()
        self.assertEqual(self.skill()["content"], supplement)
        self.assertEqual(len(self.request("GET", "/api/conversations/" + cid)[1]["messages"]), 2)
        status, data, _ = self.request("POST", path, {"content": "你好",
                                                     "settings": {"participants": ["deepseek"], "maxRounds": 1}})
        self.assertEqual(status, 200)
        self.assertIn("runId", data)
        self.wait_finished(cid)
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(self.gateway.calls[0][:2], ("zzz-trio", "deepseek"))
        self.assertIn(supplement, self.gateway.calls[0][2])
        status, undone, _ = self.request("POST", path, {"content": "/撤销设定 南宫羽"})
        self.assertEqual(status, 200)
        self.assertNotIn("runId", undone)
        self.assertEqual(self.skill()["content"], "")
        self.assertEqual(self.skill()["version"], 2)
        self.assertEqual(len(self.gateway.calls), 1)

    def test_image_only_message_is_analyzed_and_available_to_chat_models(self):
        image = self.upload()
        cid = self.create()
        status, data, _ = self.request("POST", f"/api/conversations/{cid}/messages",
                                      {"content": "", "attachments": [image["id"]], "intent": "auto",
                                       "settings": {"participants": ["gpt"], "maxRounds": 1}})
        self.assertEqual(status, 200)
        self.assertIn("runId", data)
        conversation = self.wait_finished(cid)
        user = conversation["messages"][0]
        self.assertEqual(user["content"], "")
        self.assertEqual(user["attachments"], [image])
        self.assertEqual(user["imageDescription"], "图片是一个蓝色像素。")
        self.assertEqual(self.fake_media.analyzed[0][0], [UPLOADED_PNG])
        self.assertEqual(len(self.fake_media.analyzed), 1)
        self.assertIn(user["imageDescription"], self.gateway.calls[0][2])
        self.assert_private_png(user["attachments"][0]["url"], UPLOADED_PNG)

    def test_explicit_natural_skill_commands_work_offline_and_standard_room_rejects_them(self):
        self.gateway.configured = False
        self.fake_media.configured = False
        cid = self.create("zzz-trio")
        path = f"/api/conversations/{cid}/messages"
        status, data, _ = self.request("POST", path, {"content": "更新南宫羽的设定：说话更简短。"})
        self.assertEqual(status, 200)
        self.assertNotIn("runId", data)
        self.assertEqual(self.skill()["content"], "说话更简短。")
        status, data, _ = self.request("POST", path, {"content": "撤销南宫羽的设定"})
        self.assertEqual(status, 200)
        self.assertNotIn("runId", data)
        self.assertFalse(self.skill()["canUndo"])
        self.assertEqual(self.skill()["content"], "")
        standard = self.create()
        status, error, _ = self.request("POST", f"/api/conversations/{standard}/messages",
                                        {"content": "更新南宫羽的设定：不应写入。"})
        self.assertEqual(status, 400)
        self.assertIn("error", error)
        self.assertEqual(self.request("GET", "/api/conversations/" + standard)[1]["messages"], [])
        self.assertEqual(self.gateway.calls, [])

    def test_image_only_generation_is_async_and_returns_durable_image_attachments(self):
        image = self.upload()
        cid = self.create()
        self.fake_media.release.clear()
        status, data, _ = self.request("POST", f"/api/conversations/{cid}/messages",
                                      {"content": "", "attachments": [image["id"]], "intent": "image"})
        self.assertEqual(status, 200)
        self.assertIn("runId", data)
        self.assertTrue(self.fake_media.started.wait(timeout=2))
        live = self.request("GET", "/api/bootstrap")[1]
        self.assertEqual(live["activeRuns"][cid], data["runId"])
        self.assertEqual(live["runStates"][cid]["runId"], data["runId"])
        self.assertEqual(live["runStates"][cid]["status"], "running")
        self.assertEqual(live["runStates"][cid]["providers"]["gpt"], "generating")
        self.assertEqual(self.fake_media.generated[0][1], [UPLOADED_PNG])
        self.fake_media.release.set()
        conversation = self.wait_finished(cid)
        images = [m for m in conversation["messages"] if m.get("kind") == "image"]
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["role"], "assistant")
        self.assertEqual(images[0]["provider"], "gpt")
        generated = images[0]["attachments"][0]
        self.assertNotEqual(generated["id"], image["id"])
        self.assert_private_png(generated["url"], GENERATED_PNG)
        self.assertEqual(self.gateway.calls, [])
        self.stop_server()
        self.start_server()
        stored = self.request("GET", "/api/conversations/" + cid)[1]
        self.assertEqual(stored, conversation)
        self.assert_private_png(generated["url"], GENERATED_PNG)

    def test_photo_chat_message_without_mode_generates_and_posts_image(self):
        cid = self.create("zzz-trio")
        self.fake_media.release.clear()
        status, data, _ = self.request("POST", f"/api/conversations/{cid}/messages",
                                      {"content": "大家一起合影吧"})
        self.assertEqual(status, 200)
        self.assertTrue(self.fake_media.started.wait(timeout=2))
        live = self.request("GET", "/api/bootstrap")[1]
        self.assertEqual(live["runStates"][cid]["providers"]["gpt"], "generating")
        self.fake_media.release.set()
        conversation = self.wait_finished(cid)
        images = [message for message in conversation["messages"] if message.get("kind") == "image"]
        self.assertEqual(len(images), 1)
        self.assertEqual(len(self.fake_media.generated), 1)
        self.assertEqual(len(self.fake_media.generated[0][1]), 4)
        self.assert_private_png(images[0]["attachments"][0]["url"], GENERATED_PNG)
        self.assertEqual(self.gateway.calls, [])

    def test_invalid_attachments_and_unavailable_media_do_not_append_messages(self):
        image = self.upload()
        cid = self.create()
        path = f"/api/conversations/{cid}/messages"
        for attachments in (["0" * 32], ["../outside"], [image["id"]] * 5, "not-a-list"):
            with self.subTest(attachments=attachments):
                status, data, _ = self.request("POST", path, {"content": "说明图片", "attachments": attachments})
                self.assertEqual(status, 400)
                self.assertIn("error", data)
        self.fake_media.configured = False
        status, data, _ = self.request("POST", path, {"content": "", "attachments": [image["id"]]})
        self.assertEqual(status, 400)
        self.assertIn("error", data)
        self.assertEqual(self.request("GET", "/api/conversations/" + cid)[1]["messages"], [])
        self.assertEqual(self.gateway.calls, [])
        self.assertEqual(self.fake_media.analyzed, [])


if __name__ == "__main__":
    unittest.main()
