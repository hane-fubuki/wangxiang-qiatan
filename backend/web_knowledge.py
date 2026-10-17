"""Bounded reference evidence, scoped by owner, room and speaking audience."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import threading

from backend.codex_research import public_url

MAX_RECORDS = 128
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_RECORD_BYTES = 64 * 1024
MAX_AGE = timedelta(days=30)
_LOCK = threading.RLock()
_ID = re.compile(r"[a-f0-9]{64}")
_SCOPE = re.compile(r"[A-Za-z0-9_-]{1,100}")
SCHEMA = json.loads(Path(__file__).with_name("web-knowledge.schema.json").read_text(encoding="utf-8"))


def _time(value):
    if not isinstance(value, str):
        raise ValueError("资料时间无效")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("资料时间须包含时区")
    return result


def validate_record(record):
    fields = {"schemaVersion", "kind", "authority", "status", "summary", "sources", "terms", "audience",
              "roomId", "checkedAt", "savedAt", "id", "sourceMessageId", "conversationId"}
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError("资料字段无效")
    if (type(record["schemaVersion"]) is not int or record["schemaVersion"] != 2
            or record["kind"] != "web_supplement" or record["authority"] != "reference_only"
            or record["status"] != "sourced"):
        raise ValueError("资料类型无效")
    for name, limit in (("summary", 10000), ("sourceMessageId", 100), ("conversationId", 100)):
        if not isinstance(record[name], str) or not 1 <= len(record[name]) <= limit:
            raise ValueError("资料文本无效")
    if not isinstance(record["roomId"], str) or not _SCOPE.fullmatch(record["roomId"]):
        raise ValueError("资料房间无效")
    if not isinstance(record["id"], str) or not _ID.fullmatch(record["id"]):
        raise ValueError("资料编号无效")
    for key in ("audience", "terms"):
        values = record[key]
        if (not isinstance(values, list) or not 1 <= len(values) <= (32 if key == "audience" else 8)
                or any(not isinstance(v, str) or not 1 <= len(v) <= (100 if key == "audience" else 200) for v in values)
                or len(set(values)) != len(values)):
            raise ValueError("资料范围无效")
        if key == "audience" and any(not _SCOPE.fullmatch(v) for v in values):
            raise ValueError("资料角色无效")
    sources = record["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 8:
        raise ValueError("资料来源无效")
    for source in sources:
        if (not isinstance(source, dict) or set(source) != {"title", "url"}
                or not isinstance(source["title"], str) or not 1 <= len(source["title"]) <= 240
                or not public_url(source["url"])):
            raise ValueError("资料来源无效")
    _time(record["checkedAt"])
    _time(record["savedAt"])
    if len(json.dumps(record, ensure_ascii=False).encode("utf-8")) > MAX_RECORD_BYTES:
        raise ValueError("资料超过存储上限")
    return record


class KnowledgeStore:
    def __init__(self, directory, *, max_records=MAX_RECORDS, max_bytes=MAX_TOTAL_BYTES):
        self.directory = Path(directory)
        self.max_records = max(1, min(int(max_records), MAX_RECORDS))
        self.max_bytes = max(1024, min(int(max_bytes), MAX_TOTAL_BYTES))

    @staticmethod
    def owner_for(conversation):
        owner = conversation.get("ownerId") or "conversation:" + conversation["id"]
        epoch = conversation.get("identityEpoch", "legacy")
        return owner if epoch == "legacy" else owner + ":identity:" + str(epoch)

    def folder(self, owner, room_id="wangsheng-trio"):
        if not isinstance(owner, str) or not owner or len(owner) > 1000:
            return None
        if not isinstance(room_id, str) or not _SCOPE.fullmatch(room_id):
            return None
        folder = self.directory / hashlib.sha256(owner.encode()).hexdigest() / room_id
        if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (self.directory, folder.parent, folder)):
            return None
        return folder

    def _files(self, folder):
        if not folder.exists():
            return []
        # A manually altered directory must not turn lookups into unbounded work.
        return [p for p in itertools.islice(folder.glob("*.json"), MAX_RECORDS * 4)
                if _ID.fullmatch(p.stem) and not p.is_symlink() and p.is_file()]

    def _read(self, path):
        if path.stat().st_size > MAX_RECORD_BYTES:
            raise ValueError("资料过大")
        return validate_record(json.loads(path.read_text(encoding="utf-8")))

    def save(self, conversation, message):
        report = message.get("webResearch", {})
        room = conversation.get("roomId", "standard")
        folder = self.folder(self.owner_for(conversation), room)
        if folder is None or report.get("status") != "complete" or report.get("origin") == "local":
            return None
        sources = report.get("sources", [])
        if not isinstance(sources, list):
            return None
        terms = list(dict.fromkeys(s.get("title", "").split(" - ")[0].strip()[:200]
                                  for s in sources if isinstance(s, dict) and isinstance(s.get("title"), str)))
        terms = [term for term in terms if term][:8]
        audience = message.get("audience") or conversation.get("scene", {}).get("audience")
        if not audience:
            audience = ["user", *conversation.get("settings", {}).get("participants", [])]
        record = {"schemaVersion": 2, "kind": "web_supplement", "authority": "reference_only", "status": "sourced",
                  "summary": report.get("summary"), "sources": sources, "terms": terms, "audience": list(dict.fromkeys(audience)),
                  "roomId": room, "checkedAt": report.get("checkedAt"), "savedAt": datetime.now(timezone.utc).isoformat(),
                  "sourceMessageId": message["id"], "conversationId": conversation["id"]}
        record["id"] = hashlib.sha256(json.dumps([room, record["summary"], sources, sorted(record["audience"])],
                                                ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        validate_record(record)
        age = datetime.now(timezone.utc) - _time(record["checkedAt"])
        if age > MAX_AGE or age < -timedelta(minutes=5):
            return None
        encoded = json.dumps(record, ensure_ascii=False).encode("utf-8")
        if len(encoded) > self.max_bytes:
            return None
        with _LOCK:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (record["id"] + ".json")
            if path.exists():
                try:
                    existing = self._read(path)
                    if _time(existing["checkedAt"]) >= _time(record["checkedAt"]):
                        return record["id"]
                except (OSError, ValueError, TypeError):
                    pass
            files = []
            for entry in self._files(folder):
                if entry == path:
                    continue
                try:
                    old = self._read(entry)
                    if datetime.now(timezone.utc) - _time(old["checkedAt"]) > MAX_AGE:
                        entry.unlink()
                    else:
                        files.append((entry, _time(old["savedAt"]), entry.stat().st_size))
                except (ValueError, TypeError):
                    # Corrupt managed records count against storage too; remove
                    # them instead of allowing unlimited invalid-file buildup.
                    entry.unlink(missing_ok=True)
                except OSError:
                    continue
            files.sort(key=lambda item: item[1])
            total = sum(item[2] for item in files)
            while files and (len(files) >= self.max_records or total + len(encoded) > self.max_bytes):
                entry, _, size = files.pop(0)
                entry.unlink()
                total -= size
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(encoded)
            os.replace(temporary, path)
        return record["id"]

    def lookup(self, owner, audience, text, room_id="wangsheng-trio"):
        folder = self.folder(owner, room_id)
        if folder is None or not isinstance(text, str) or not audience:
            return []
        found = []
        now = datetime.now(timezone.utc)
        with _LOCK:
            for path in self._files(folder):
                try:
                    record = self._read(path)
                    age = now - _time(record["checkedAt"])
                    if (record["roomId"] != room_id or not set(audience) <= set(record["audience"])
                            or age > MAX_AGE or age < -timedelta(minutes=5)):
                        continue
                    if any(len(term) >= 2 and term in text for term in record["terms"]):
                        found.append(record)
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        return sorted(found, key=lambda record: record["checkedAt"], reverse=True)[:3]
