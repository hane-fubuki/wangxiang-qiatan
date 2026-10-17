"""Browser identity for new private rooms, without changing legacy shared chats."""
import copy
from http.cookies import SimpleCookie, CookieError
import json
from pathlib import Path
import re
import secrets
import threading

COOKIE = "tavern_visitor"


def cookie_identity(value):
    if not isinstance(value, str) or len(value) > 8192:
        return None
    if sum(p.strip().partition("=")[0] == COOKIE for p in value.split(";")) != 1:
        return None
    jar = SimpleCookie()
    try:
        jar.load(value)
        token = jar[COOKIE].value
    except (CookieError, KeyError, ValueError):
        return None
    return token if re.fullmatch(r"[a-f0-9]{64}", token) else None


def new_identity():
    return secrets.token_hex(32)


def visitor_cookie(token, secure=False):
    return f"{COOKIE}={token}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict" + ("; Secure" if secure else "")


def can_access(conversation, visitor):
    return not conversation.get("ownerId") or conversation["ownerId"] == visitor


def public_conversation(conversation):
    result = copy.deepcopy(conversation)
    result.pop("ownerId", None)
    return result


class MediaAccess:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.owners = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        if not isinstance(self.owners, dict):
            raise ValueError("图片访问记录无效，原文件已保留。")

    def allowed(self, identifier, visitor):
        with self.lock:
            owner = self.owners.get(identifier)
            return not owner or owner == visitor

    def claim(self, identifiers, owner):
        with self.lock:
            changed = False
            for identifier in identifiers:
                if not re.fullmatch(r"[a-f0-9]{32}", identifier):
                    raise ValueError("图片编号无效")
                if identifier not in self.owners or not owner:
                    self.owners[identifier] = owner
                    changed = True
            if changed:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix(".tmp")
                temporary.write_text(json.dumps(self.owners), encoding="utf-8")
                temporary.replace(self.path)
