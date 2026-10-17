"""Scene boundaries are separate from browser ownership and legacy rooms."""
import tempfile
import unittest

from backend.scenes import parse_scene_command, public_scene, shared_conversation, visible_conversation
from backend.store import Store, make_message
from backend.visitors import MediaAccess, can_access, cookie_identity, new_identity, public_conversation, visitor_cookie


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(self.directory.name)
        self.conversation = self.store.create("wangsheng-trio", owner_id="a" * 64)
        self.cid = self.conversation["id"]

    def test_aliases_ids_and_limits(self):
        scene, prompt = parse_scene_command("/私聊 若小姐 | 喝茶吗")
        self.assertEqual(scene["audience"], ["user", "gpt"])
        self.assertEqual(prompt, "喝茶吗")
        self.assertEqual(parse_scene_command("/悄悄话 deepseek gpt")[0]["audience"], ["deepseek", "gpt"])
        self.assertEqual(parse_scene_command("/全桌")[0]["audience"], public_scene("wangsheng-trio")["audience"])
        self.assertEqual(len(parse_scene_command("/悄悄话 user deepseek gemini gpt paimon xiao xiangling zibai")[0]["audience"]), 8)
        for command in ("/私聊 我", "/悄悄话 user user", "/悄悄话 nobody gpt", "/全桌 胡桃"):
            with self.subTest(command=command), self.assertRaises(ValueError):
                parse_scene_command(command)
        self.assertEqual(parse_scene_command("/私聊 GPT", "standard")[0]["audience"], ["user", "gpt"])

    def test_shared_tools_cannot_leak_private_history_when_audience_changes(self):
        self.store.append(self.cid, make_message("user", "公开话题"))
        private, _ = parse_scene_command("/私聊 钟离")
        self.store.set_scene(self.cid, private)
        self.store.append(self.cid, make_message("user", "私下的图片", attachments=[{"id": "1" * 32}]))
        self.store.append(self.cid, make_message("assistant", "私下回答", provider="deepseek"))
        self.store.set_scene(self.cid, public_scene("wangsheng-trio"))
        latest = self.store.append(self.cid, make_message("user", "回桌聊天"))
        self.assertEqual([m["content"] for m in shared_conversation(latest)["messages"]], ["公开话题", "回桌聊天"])
        self.assertEqual(len(visible_conversation(latest, "deepseek")["messages"]), 4)
        self.assertEqual(len(visible_conversation(latest, "gemini")["messages"]), 2)
        self.assertEqual(len(self.store.get(self.cid)["messages"]), 4)

    def test_director_and_persisted_scene_do_not_migrate_legacy(self):
        scene, _ = parse_scene_command("/悄悄话 钟离 若娜瓦")
        self.store.set_scene(self.cid, scene)
        self.store.append(self.cid, make_message("user", "继续聊刚才的话题"))
        restored = Store(self.directory.name).get(self.cid)
        self.assertTrue(restored["messages"][-1]["director"])
        self.assertEqual(shared_conversation(restored)["messages"][-1]["audience"], ["deepseek", "gpt"])
        old = self.store.create("zzz-trio")
        # Simulate a legacy message saved before audience metadata existed.
        self.store.items[old["id"]]["identityEpoch"] = "legacy"
        self.store.items[old["id"]]["messages"].append(make_message("user", "你好"))
        self.store._save()
        old = Store(self.directory.name).get(old["id"])
        self.assertNotIn("ownerId", old)
        self.assertNotIn("audience", old["messages"][0])
        self.assertEqual(shared_conversation(old), old)

    def test_owner_and_invalid_scene_validation(self):
        self.assertTrue(can_access(self.conversation, "a" * 64))
        self.assertFalse(can_access(self.conversation, "b" * 64))
        self.assertNotIn("ownerId", public_conversation(self.conversation))
        self.assertIn("ownerId", self.conversation)
        for scene in ([], {"kind": "private", "audience": [[], "user"]},
                      {"kind": "private", "audience": ["user", "gpt"], "id": "../", "label": "bad"}):
            with self.assertRaises(ValueError):
                self.store.set_scene(self.cid, scene)


class VisitorTests(unittest.TestCase):
    def test_cookie_is_single_valid_identity(self):
        token = new_identity()
        self.assertEqual(cookie_identity(visitor_cookie(token)), token)
        self.assertIn("Secure", visitor_cookie(token, secure=True))
        for value in ("", "tavern_visitor=short", "tavern_visitor=" + "A" * 64,
                      f"tavern_visitor={token}; tavern_visitor={token}", "x" * 8193):
            self.assertIsNone(cookie_identity(value))
        self.assertEqual(cookie_identity(f"auth=not-forwarded; tavern_visitor={token}"), token)

    def test_media_ownership_persists_and_explicit_shared_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            access = MediaAccess(directory + "/media-access.json")
            picture = "1" * 32
            access.claim([picture], "a" * 64)
            self.assertFalse(access.allowed(picture, "b" * 64))
            access.claim([picture], "b" * 64)
            self.assertFalse(access.allowed(picture, "b" * 64))
            restored = MediaAccess(access.path)
            self.assertTrue(restored.allowed(picture, "a" * 64))
            self.assertTrue(restored.allowed("2" * 32, "b" * 64))
            restored.claim([picture], None)
            self.assertTrue(MediaAccess(access.path).allowed(picture, "b" * 64))


if __name__ == "__main__":
    unittest.main()
