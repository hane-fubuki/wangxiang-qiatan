"""Controlled protagonist images use portable references and scoped history.

All conversations, media outputs, and skill revisions live in temporary stores.
The real image orchestration/HTTP handler use fake transports and no model calls.
"""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from app import create_server
from backend import protagonists
from backend.media import MediaStore
from backend.rooms import get_room, public_rooms
from backend.scenes import parse_scene_command, public_scene
from backend.skills import SkillStore
from backend.store import Store, make_message
from tests.test_features import FakeMedia, ObservedEngine, png
from tests.test_wangsheng_engine import Gateway


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "web" / "assets"


class ProtagonistMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "history")
        self.media = MediaStore(self.root / "media")
        self.skills = SkillStore(self.root / "skills")
        self.output = self.root / "generated.png"
        self.output.write_bytes(png())
        self.codex = FakeMedia(self.output)
        self.gateway = Gateway()
        self.events = []
        self.engine = ObservedEngine(self.store, self.gateway, lambda e, p: self.events.append((e, p)),
                                     skills=self.skills, media=self.media, codex_media=self.codex)
        self.addCleanup(self.engine.stop_all)

    def conversation(self, room_id, role):
        cid = self.store.create(room_id)["id"]
        member = next(slot for slot, info in get_room(room_id)["characters"].items() if not info.get("optional"))
        self.store.update(cid, {"settings": {"participants": [member], "userRole": role,
                                            "interactionMode": "chat", "maxRounds": 1, "webSearch": "off"}})
        return cid, member

    def generate(self, cid, text):
        count = len(self.codex.generation_calls)
        result = self.engine.start(cid, text)
        self.assertTrue(self.engine.wait_finished(result), result)
        self.assertEqual(len(self.codex.generation_calls), count + 1)
        messages = self.store.get(cid)["messages"]
        self.assertFalse([m for m in messages if m.get("kind") == "error"], messages)
        generated = messages[-1]
        self.assertEqual(generated.get("kind"), "image")
        self.assertTrue(generated.get("attachments"))
        for attachment in generated["attachments"]:
            self.assertTrue(self.media.path(attachment["id"]).is_relative_to(self.root))
        self.assertNotIn(str(self.root), json.dumps(generated))
        self.assertFalse(self.gateway.calls, "image generation must not invoke chat models")
        self.assertFalse(self.codex.analysis_calls)
        prompt, paths, _ = self.codex.generation_calls[-1]
        return generated, prompt, paths

    def test_human_lumine_and_belle_use_their_own_stand_without_a_second_user_avatar(self):
        cases = [("wangsheng-trio", "lumine")]
        cases += [(room["id"], "belle") for room in public_rooms()]
        for room_id, role in cases:
            with self.subTest(room=room_id, role=role):
                cid, member = self.conversation(room_id, role)
                marker = f"PRIVATE_IMAGE_CONTEXT_{room_id}_{role}"
                private, _ = parse_scene_command(f"/私聊 {member}", room_id, user_role=role)
                self.store.set_scene(cid, private)
                self.store.append(cid, make_message("user", marker))
                self.store.set_scene(cid, public_scene(room_id, role))
                custom = "MY_VISUAL_NOTE_" + role
                self.skills.update(role, custom)
                for request, expected in (("画我的头像", {role}), ("大家一起合影吧", {member, role})):
                    with self.subTest(request=request):
                        image, prompt, paths = self.generate(cid, request)
                        self.assertTrue(image["imageContext"]["includeUser"])
                        self.assertEqual(set(image["imageContext"]["subjects"]), expected)
                        self.assertEqual(image["imageContext"]["subjects"].count(role), 1)
                        names = [path.name for path in paths]
                        self.assertEqual(names.count(f"protagonist-{role}-stand.png"), 1)
                        self.assertNotIn("user-avatar.png", names)
                        self.assertIn(f"用户当前扮演{protagonists.NAMES[role]}", prompt)
                        self.assertIn(custom, prompt)
                        self.assertNotIn(marker, prompt, "private scene must not enter a public image request")

    def test_named_exclusion_applies_to_controlled_user_and_does_not_return_through_edits(self):
        cases = [("wangsheng-trio", "lumine", "荧")]
        cases += [(room["id"], "belle", alias)
                  for room in public_rooms() for alias in ("铃", "玲")]
        for room_id, role, alias in cases:
            with self.subTest(room=room_id, role=role, alias=alias):
                cid, member = self.conversation(room_id, role)
                first, _, _ = self.generate(cid, "大家一起合照吧")
                self.assertIn(role, first["imageContext"]["subjects"])
                for request in (f"修改这张合照，不要{alias}", "背景改成海边"):
                    image, prompt, paths = self.generate(cid, request)
                    self.assertFalse(image["imageContext"]["includeUser"])
                    self.assertEqual(image["imageContext"]["subjects"], [member])
                    self.assertNotIn(f"protagonist-{role}-stand.png", [path.name for path in paths])
                    self.assertNotIn("user-avatar.png", [path.name for path in paths])
                    self.assertTrue(image["imageContext"]["edits"])

                # A new group request with an explicit named exclusion must
                # behave the same as editing a prior picture of that person.
                fresh, _ = self.conversation(room_id, role)
                image, prompt, paths = self.generate(fresh, f"大家一起合照，不要{alias}")
                self.assertFalse(image["imageContext"]["includeUser"])
                self.assertEqual(image["imageContext"]["subjects"], [member])
                self.assertNotIn(f"protagonist-{role}-stand.png", [path.name for path in paths])
                self.assertNotIn("user-avatar.png", [path.name for path in paths])


class ProtagonistAssetHttpTests(unittest.TestCase):
    def test_four_public_portraits_are_served_but_reference_documents_stay_private(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "fake-generated.png"
            output.write_bytes(png())
            gateway = Gateway()
            media = FakeMedia(output)
            server = create_server(port=0, data_dir=root / "app", gateway=gateway, codex_media=media)
            runner = threading.Thread(target=server.serve_forever, daemon=True)
            runner.start()
            try:
                for role in ("lumine", "belle"):
                    for kind in ("stand", "avatar"):
                        name = f"protagonist-{role}-{kind}.png"
                        with self.subTest(asset=name):
                            expected = (ASSETS / name).read_bytes()
                            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                            try:
                                connection.request("GET", "/assets/" + name)
                                response = connection.getresponse()
                                body = response.read()
                                self.assertEqual(response.status, 200)
                                self.assertEqual(response.getheader("Content-Type"), "image/png")
                                self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
                                self.assertEqual(body, expected)
                                self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n"))
                            finally:
                                connection.close()
                for path in ("/resources/protagonists/lumine/characters/lumine.md",
                             "/resources/protagonists/belle/qa.md",
                             "/assets/protagonist-belle-avatar.png.bak",
                             "/assets/../resources/protagonists/belle/visual.md"):
                    with self.subTest(private_path=path):
                        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                        try:
                            connection.request("GET", path)
                            response = connection.getresponse()
                            body = response.read()
                            self.assertEqual(response.status, 404)
                            self.assertNotIn(str(root).encode(), body)
                        finally:
                            connection.close()
                self.assertEqual(server.store.list(), [])
                self.assertEqual(gateway.calls, [])
                self.assertEqual(media.generation_calls, [])
                self.assertEqual(media.analysis_calls, [])
            finally:
                server.engine.stop_all()
                server.starters.cancel_all()
                server.shutdown()
                server.server_close()
                runner.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
