from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from backend.web_knowledge import KnowledgeStore, validate_record


class WebKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = KnowledgeStore(self.root)
        self.conversation = {"id": "conversation-a", "ownerId": "owner-a", "roomId": "wangsheng-trio"}
        self.message = {"id": "message-a", "audience": ["user", "deepseek"], "webResearch": {
            "status": "complete", "summary": "公开资料片段", "sources": [{"title": "测试名词", "url": "https://example.org/lore"}],
            "checkedAt": datetime.now(timezone.utc).isoformat()}}

    def lookup(self, owner="owner-a", audience=None, room="wangsheng-trio"):
        return self.store.lookup(owner, audience or ["deepseek"], "测试名词", room)

    def test_owner_room_and_audience_are_independent_scopes(self):
        self.store.save(self.conversation, self.message)
        self.assertEqual(len(self.lookup()), 1)
        self.assertEqual(self.lookup(owner="owner-b"), [])
        self.assertEqual(self.lookup(audience=["gemini"]), [])
        self.assertEqual(self.lookup(audience=["deepseek", "gemini"]), [])
        self.assertEqual(self.lookup(room="zzz-trio"), [])

    def test_absent_owner_uses_conversation_identity(self):
        self.conversation.pop("ownerId")
        self.store.save(self.conversation, self.message)
        self.assertTrue(self.lookup(owner="conversation:conversation-a"))
        self.assertFalse(self.lookup(owner="conversation:conversation-b"))

    def test_idempotent_save_and_refresh(self):
        key = self.store.save(self.conversation, self.message)
        self.assertEqual(key, self.store.save(self.conversation, self.message))
        self.assertEqual(len(list(self.root.rglob("*.json"))), 1)
        old = self.lookup()[0]
        self.message["webResearch"]["checkedAt"] = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        self.assertEqual(key, self.store.save(self.conversation, self.message))
        self.assertGreater(self.lookup()[0]["checkedAt"], old["checkedAt"])

    def test_local_failed_and_cancelled_reports_do_not_archive(self):
        for report in ({"status": "failed"}, {"status": "cancelled"}, {**self.message["webResearch"], "origin": "local"}):
            self.assertIsNone(self.store.save(self.conversation, {**self.message, "webResearch": report}))
        self.assertFalse(list(self.root.rglob("*.json")))

    def test_old_and_future_records_are_not_used(self):
        for delta in (timedelta(days=-31), timedelta(hours=1)):
            self.message["webResearch"]["checkedAt"] = (datetime.now(timezone.utc) + delta).isoformat()
            self.store.save(self.conversation, self.message)
            self.assertEqual(self.lookup(), [])

    def test_count_and_byte_limits(self):
        self.store = KnowledgeStore(self.root, max_records=3, max_bytes=4000)
        for number in range(12):
            self.message["webResearch"]["summary"] = f"片段{number}" + "x" * 700
            self.store.save(self.conversation, self.message)
        paths = list(self.root.rglob("*.json"))
        self.assertLessEqual(len(paths), 3)
        self.assertLessEqual(sum(path.stat().st_size for path in paths), 4000)
        self.assertTrue(any("片段11" in r["summary"] for r in self.lookup()))

    def test_corrupt_oversized_or_mismatched_records_are_not_used(self):
        self.store.save(self.conversation, self.message)
        path = next(self.root.rglob("*.json"))
        record = json.loads(path.read_text(encoding="utf-8"))
        record["roomId"] = "zzz-trio"
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(self.lookup(), [])
        path.write_bytes(b"x" * 70000)
        self.assertEqual(self.lookup(), [])
        path.write_bytes(b"{")
        self.assertEqual(self.lookup(), [])

    def test_other_rooms_and_grok_can_store_without_expanding_access(self):
        self.conversation["roomId"] = "standard"
        self.message["audience"] = ["user", "grok"]
        self.store.save(self.conversation, self.message)
        self.assertTrue(self.lookup(audience=["grok"], room="standard"))
        self.assertFalse(self.lookup(room="standard"))
        self.assertIsNone(self.store.folder("owner-a", "../outside"))


if __name__ == "__main__":
    unittest.main()
