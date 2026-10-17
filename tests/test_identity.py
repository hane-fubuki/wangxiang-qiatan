"""User role control never changes historical authors or leaks identity epochs."""
import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch

from app import create_server
from backend.engine import Run
from backend.identity import (identity_instruction, normalized_identity, user_actor,
                              user_display_name)
from backend.rooms import public_rooms
from backend.scenes import (current_scene, message_matches_scene, parse_scene_command,
                            public_scene, scene_instruction, shared_conversation,
                            visible_conversation)
from backend.store import Store, default_settings, make_message, validate_settings


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.chat = self.store.create("wangsheng-trio")
        self.cid = self.chat["id"]

    def test_optional_guests_are_available_but_not_forced_into_existing_or_new_members(self):
        for room in public_rooms():
            with self.subTest(room=room["id"]):
                settings = default_settings(room["id"])
                self.assertNotIn("belle", settings["participants"])
                self.assertNotIn("lumine", settings["participants"])
                selected = validate_settings({}, {**settings, "participants": settings["participants"][:1]}, room["id"])
                self.assertEqual(selected["participants"], settings["participants"][:1])
                self.assertEqual(selected["userRole"], "lumine" if room["id"] == "wangsheng-trio" else "self")
                self.assertEqual(selected["interactionMode"], "chat")

    def test_user_role_is_removed_from_ai_and_no_available_ai_is_an_error(self):
        settings = validate_settings({"participants": ["belle", "gemini"], "userRole": "belle"}, room_id="wangsheng-trio")
        self.assertEqual(settings["participants"], ["gemini"])
        with self.assertRaisesRegex(ValueError, "未知的聊天室角色"):
            validate_settings({"participants": ["lumine", "gemini"]}, room_id="wangsheng-trio")
        with self.assertRaisesRegex(ValueError, "至少选择另一位"):
            validate_settings({"participants": ["belle"], "userRole": "belle"})
        with self.assertRaisesRegex(ValueError, "仅可在往生堂"):
            validate_settings({"userRole": "lumine"}, room_id="zzz-trio")

    def test_scene_mode_releases_role_but_rejects_explicit_conflicting_selection(self):
        role = validate_settings({"userRole": "lumine"}, room_id="wangsheng-trio")
        scene = validate_settings({"interactionMode": "scene"}, role, "wangsheng-trio")
        self.assertEqual((scene["userRole"], scene["interactionMode"]), ("self", "scene"))
        for values in ({"interactionMode": "scene", "userRole": "lumine"},
                       {"userRole": []}, {"interactionMode": "invalid"}, {"userRole": "派蒙"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_settings(values, room_id="wangsheng-trio")

    def test_identity_switch_starts_a_new_context_and_preserves_authors(self):
        self.store.update(self.cid, {"settings": {"userRole": "self"}})
        old = make_message("user", "我用自己的身份说的话")
        before = self.store.append(self.cid, old)
        role = self.store.update(self.cid, {"settings": {"userRole": "lumine"}})
        self.assertNotEqual(role["identityEpoch"], before["identityEpoch"])
        self.assertEqual(shared_conversation(role)["messages"], [])
        self.assertEqual(user_display_name(role, role["messages"][0]), "你")
        self.assertNotIn("lumine", current_scene(role)["audience"])
        role = self.store.append(self.cid, make_message("user", "该去冒险了。"))
        self.assertEqual(role["messages"][-1]["actor"], {"mode": "chat", "characterId": "lumine", "name": "荧"})
        scene = self.store.update(self.cid, {"settings": {"interactionMode": "scene"}})
        self.assertNotEqual(scene["identityEpoch"], role["identityEpoch"])
        scene = self.store.append(self.cid, make_message("user", "两人在门口遇见。"))
        self.assertTrue(scene["messages"][-1]["director"])
        self.assertEqual(scene["messages"][-1]["actor"]["name"], "场外导演")
        again = self.store.update(self.cid, {"settings": {"interactionMode": "chat", "userRole": "lumine"}})
        self.assertEqual(shared_conversation(again)["messages"], [])
        self.assertEqual(len(again["messages"]), 3)
        restored = Store(self.temp.name).get(self.cid)
        self.assertEqual([user_display_name(restored, message) for message in restored["messages"]], ["你", "荧", "场外导演"])

    def test_participant_changes_and_continuing_scenes_do_not_reset_identity(self):
        public = self.store.append(self.cid, make_message("user", "桌上的话题"))
        private, _ = parse_scene_command("/私聊 钟离")
        self.store.set_scene(self.cid, private)
        self.store.append(self.cid, make_message("user", "只给钟离的话"))
        latest = self.store.update(self.cid, {"settings": {"participants": ["deepseek", "belle"]}})
        self.assertEqual(latest["identityEpoch"], public["identityEpoch"])
        self.assertEqual([m["content"] for m in visible_conversation(latest, "deepseek")["messages"]], ["桌上的话题", "只给钟离的话"])
        self.assertEqual([m["content"] for m in visible_conversation(latest, "belle")["messages"]], ["桌上的话题"])
        reset = self.store.update(self.cid, {"settings": {"userRole": "belle"}})
        self.assertEqual(current_scene(reset)["kind"], "public")
        self.assertFalse(message_matches_scene(reset, latest["messages"][0]))

    def test_public_history_can_reach_new_guest_but_old_private_history_cannot(self):
        public = make_message("user", "新增角色前的公开发言", audience=["user", "gemini"], scene={"kind": "public"})
        self.store.append(self.cid, public)
        private = make_message("user", "私密发言", audience=["user", "gemini"], scene={"kind": "private"})
        chat = self.store.append(self.cid, private)
        self.assertEqual([m["content"] for m in visible_conversation(chat, "belle")["messages"]], [public["content"]])

    def test_scene_aliases_follow_user_control_without_merging_ai_protagonists(self):
        self.assertEqual(parse_scene_command("/悄悄话 荧 玲")[0]["audience"], ["user", "belle"])
        self.assertEqual(parse_scene_command("/悄悄话 荧 钟离", "wangsheng-trio", "lumine")[0]["audience"], ["user", "deepseek"])
        self.assertEqual(parse_scene_command("/悄悄话 旅行者 钟离")[0]["audience"], ["user", "deepseek"])
        for command in ("/私聊 荧", "/悄悄话 荧 钟离", "/悄悄话 旅行者 钟离"):
            with self.subTest(command=command), self.assertRaises(ValueError):
                parse_scene_command(command, "wangsheng-trio", "self")
        with self.assertRaises(ValueError):
            parse_scene_command("/悄悄话 荧 user", "wangsheng-trio", "lumine")
        with self.assertRaises(ValueError):
            parse_scene_command("/私聊 荧", "zzz-trio")

    def test_actor_metadata_is_assigned_once_and_stale_epoch_cannot_append(self):
        forged = make_message("user", "你好", actor={"characterId": "self", "name": "你"})
        self.store.append(self.cid, forged)
        self.assertEqual(forged["actor"]["characterId"], "lumine")
        for change in ({"actor": {"characterId": "belle"}}, {"identityEpoch": "legacy"}, {"role": "assistant"}, {"director": True}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "不可修改"):
                self.store.update_message(self.cid, forged["id"], change)
        self.store.update(self.cid, {"settings": {"userRole": "belle"}})
        with self.assertRaisesRegex(ValueError, "已结束"):
            self.store.append(self.cid, make_message("assistant", "过期回应", identityEpoch=forged["identityEpoch"]))

    def test_legacy_and_damaged_saved_identity_fallback_without_relabeling_history(self):
        raw = self.store.items[self.cid]
        raw["settings"].pop("userRole")
        raw["settings"].pop("interactionMode")
        raw.pop("identityEpoch")
        raw["messages"].append(make_message("user", "旧版本用户"))
        self.store._save()
        restored = Store(self.temp.name).get(self.cid)
        self.assertEqual(restored["identityEpoch"], "legacy")
        self.assertEqual(restored["settings"]["userRole"], "lumine")
        self.assertEqual(len(shared_conversation(restored)["messages"]), 1)
        self.assertNotIn("actor", restored["messages"][0])
        raw["settings"]["userRole"] = "lumine"
        self.store._save()
        restored = Store(self.temp.name).get(self.cid)
        self.assertEqual(restored["settings"]["userRole"], "self")
        self.assertEqual(shared_conversation(restored)["messages"], [])
        self.assertEqual(user_display_name(restored, restored["messages"][0]), "荧")
        self.assertEqual(normalized_identity({"userRole": [], "interactionMode": "chat"}), {"userRole": "self", "interactionMode": "chat"})

    def test_explicit_self_and_historical_actor_are_not_overwritten_by_room_default(self):
        self.assertEqual(self.chat["settings"]["userRole"], "lumine")
        self.store.update(self.cid, {"settings": {"userRole": "self"}})
        chat = self.store.append(self.cid, make_message("user", "我选择自己"))
        restored = Store(self.temp.name).get(self.cid)
        self.assertEqual(restored["settings"]["userRole"], "self")
        self.assertEqual(restored["identityEpoch"], chat["identityEpoch"])
        self.assertEqual(user_display_name(restored, restored["messages"][-1]), "你")
        self.assertEqual(normalized_identity({}, "wangsheng-trio"), {"userRole": "lumine", "interactionMode": "chat"})

    def test_prompt_instructions_distinguish_director_and_user_owned_role(self):
        role = self.store.update(self.cid, {"settings": {"userRole": "lumine"}})
        self.assertIn("荧由用户独占扮演", identity_instruction(role, "belle"))
        self.assertIn("不得代写荧", identity_instruction(role, "gemini"))
        self.assertEqual(scene_instruction(role, "deepseek").count("荧"), 1)
        scene = self.store.update(self.cid, {"settings": {"interactionMode": "scene"}})
        self.assertIn("用户是场外导演", identity_instruction(scene, "belle"))
        self.assertIn("用户当前输入是场外导演提示", scene_instruction(scene, "belle"))
        self.assertEqual(user_actor(scene)["characterId"], "self")


class IdentityHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_server import FakeGateway
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = create_server(port=0, data_dir=cls.temp.name, gateway=FakeGateway())
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.engine.stop_all()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)
        cls.temp.cleanup()

    def request(self, path, payload):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            connection.request("PATCH" if "/conversations/" in path else "POST", path,
                               json.dumps(payload).encode(), {"Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_invalid_patch_is_validated_before_stopping_or_mutating(self):
        chat = self.server.store.create("wangsheng-trio")
        run = Run("f" * 32, chat["id"])
        self.server.engine.active[chat["id"]] = run
        for payload in ({"title": "", "settings": {"userRole": "lumine"}},
                        {"settings": {"interactionMode": "scene", "userRole": "belle"}},
                        {"settings": {"userRole": "unknown"}}):
            with self.subTest(payload=payload):
                status, _ = self.request("/api/conversations/" + chat["id"], payload)
                self.assertEqual(status, 400)
                self.assertFalse(run.cancel.is_set())
                self.assertEqual(self.server.store.get(chat["id"]), chat)
        self.server.engine.stop_conversation(chat["id"])

    def test_valid_patch_cancels_old_run_before_new_identity_is_saved(self):
        chat = self.server.store.create("wangsheng-trio")
        run = Run("e" * 32, chat["id"])
        self.server.engine.active[chat["id"]] = run
        with patch.object(self.server.store, "update", wraps=self.server.store.update) as update:
            status, changed = self.request("/api/conversations/" + chat["id"], {"settings": {"userRole": "belle"}})
            self.assertEqual(status, 200)
            self.assertTrue(run.cancel.is_set())
            update.assert_called_once()
        self.assertNotEqual(changed["identityEpoch"], chat["identityEpoch"])
        self.assertFalse(self.server.engine._message(run, make_message("assistant", "旧角色回复")))
        self.assertEqual(self.server.store.get(chat["id"])["messages"], [])

    def test_skill_routes_accept_protagonists_and_enforce_room_scope(self):
        for role, room, expected in (("lumine", "zzz-trio", 400), ("lumine", "wangsheng-trio", 200),
                                     ("belle", "standard", 200), ("belle", "zzz-trio", 200)):
            with self.subTest(role=role, room=room):
                version = self.server.skills.get(role)["version"]
                status, _ = self.request("/api/skills/" + role, {"roomId": room, "expectedVersion": version, "content": "简短自然回应。"})
                self.assertEqual(status, expected)


if __name__ == "__main__":
    unittest.main()
