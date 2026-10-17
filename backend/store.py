"""Atomic local conversation storage. Never stores provider credentials."""
from __future__ import annotations

import copy
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.rooms import get_room, validate_room
from backend.identity import (IDENTITY_DEFAULTS, identity_changed, identity_epoch,
                              default_identity, normalized_identity, user_actor, validate_identity)


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


DEFAULT_SETTINGS = {"participants": ["deepseek", "gemini", "gpt", "grok"], "mode": "auto", "maxRounds": 3,
                    "models": {}, "reasoning": "auto", "webSearch": "auto", **IDENTITY_DEFAULTS}


def default_settings(room_id="standard"):
    return {**copy.deepcopy(DEFAULT_SETTINGS), **default_identity(room_id), "participants": [key for key, character in
            get_room(room_id)["characters"].items() if not character.get("optional")]}


def validate_settings(value, current=None, room_id="standard"):
    if not isinstance(value, dict):
        raise ValueError("会话设置格式不正确")
    characters = get_room(room_id)["characters"]
    result = {**default_settings(room_id), **(current or {}), **value}
    identity = validate_identity(value, current, room_id)
    members = result.get("participants")
    if not isinstance(members, list) or not members or len(members) > len(characters):
        raise ValueError(f"请选择 1 到 {len(characters)} 个角色")
    if any(not isinstance(p, str) or p not in characters for p in members):
        raise ValueError("未知的聊天室角色")
    members = [member for member in members if member != identity["userRole"]]
    if not members:
        raise ValueError("用户扮演的角色不能同时由 AI 控制，请至少选择另一位 AI 角色。")
    if result.get("mode") not in ("auto", "all"):
        raise ValueError("未知的对话模式")
    if result.get("reasoning") not in ("auto", "deep"):
        raise ValueError("未知的思考模式")
    if result.get("webSearch") not in ("auto", "always", "off"):
        raise ValueError("未知的联网查询方式")
    rounds = result.get("maxRounds")
    if type(rounds) is not int or not 1 <= rounds <= 8:
        raise ValueError("交流轮数须为 1 到 8")
    models = result.get("models", {})
    if not isinstance(models, dict) or len(models) > len(characters):
        raise ValueError("角色模型配置格式不正确")
    for slot, route in models.items():
        if slot not in characters or not isinstance(route, dict) or set(route) != {"providerId", "model"}:
            raise ValueError("角色模型配置格式不正确")
        if route["providerId"] not in ("deepseek", "gemini", "gpt", "grok", "custom"):
            raise ValueError("未知的模型提供商")
        if not isinstance(route["model"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", route["model"]):
            raise ValueError("模型名称格式不正确")
    return {"participants": list(dict.fromkeys(members)), "mode": result["mode"], "maxRounds": rounds,
            "models": copy.deepcopy(models), "reasoning": result["reasoning"], "webSearch": result["webSearch"], **identity}


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "conversations.json"
        self.lock = threading.RLock()
        self.items = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or not isinstance(data.get("conversations"), list):
                    raise ValueError("invalid storage")
                self.items = {c["id"]: {**c, "roomId": validate_room(c.get("roomId", "standard"))}
                              for c in data["conversations"]}
                for item in self.items.values():
                    self._restore_identity(item)
            except (ValueError, KeyError, TypeError) as exc:
                raise RuntimeError(f"无法读取聊天记录，原文件已保留：{self.path}") from exc

    @staticmethod
    def _restore_identity(item):
        from backend.scenes import public_scene
        settings = item.get("settings", {})
        if not isinstance(settings, dict):
            settings = default_settings(item["roomId"])
        normalized = normalized_identity(settings, item["roomId"])
        explicit = {key: settings[key] for key in IDENTITY_DEFAULTS if key in settings}
        malformed = bool(explicit) and explicit != normalized
        item["settings"] = {**settings, **normalized}
        # Legacy messages retain their room's original default identity.
        if malformed or identity_epoch(item) == "invalid":
            item["identityEpoch"] = uid()
            item["scene"] = public_scene(item["roomId"])
        else:
            item.setdefault("identityEpoch", "legacy" if normalized == default_identity(item["roomId"]) else uid())
        role = normalized["userRole"]
        if isinstance(item["settings"].get("participants"), list):
            item["settings"]["participants"] = [p for p in item["settings"]["participants"] if p != role and p != "lumine"]
        if isinstance(item["settings"].get("models"), dict):
            item["settings"]["models"].pop("lumine", None)

    def _save(self):
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump({"version": 1, "conversations": list(self.items.values())}, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)

    def list(self):
        with self.lock:
            return copy.deepcopy(sorted(self.items.values(), key=lambda c: c["updatedAt"], reverse=True))

    def get(self, identifier):
        with self.lock:
            if identifier not in self.items:
                raise KeyError("会话不存在")
            return copy.deepcopy(self.items[identifier])

    def create(self, room_id="standard", owner_id=None):
        with self.lock:
            room_id = validate_room(room_id)
            timestamp = now()
            item = {"id": uid(), "title": "新的对话", "createdAt": timestamp, "updatedAt": timestamp,
                    "messages": [], "settings": default_settings(room_id), "roomId": room_id,
                    "identityEpoch": uid()}
            if owner_id is not None:
                if not isinstance(owner_id, str) or not re.fullmatch(r"[a-f0-9]{64}", owner_id):
                    raise ValueError("访客标识无效")
                item["ownerId"] = owner_id
            self.items[item["id"]] = item
            self._save()
            return copy.deepcopy(item)

    def validate_update(self, identifier, changes):
        with self.lock:
            self.get(identifier)
            item = self.items[identifier]
            if not isinstance(changes, dict):
                raise ValueError("会话修改格式不正确")
            if "roomId" in changes and validate_room(changes["roomId"]) != item["roomId"]:
                raise ValueError("会话创建后不能更换聊天室，请在目标聊天室新建对话。")
            validated = {}
            if "settings" in changes:
                validated["settings"] = validate_settings(changes["settings"], item["settings"], item["roomId"])
            if "title" in changes:
                title = changes["title"]
                if not isinstance(title, str) or not title.strip() or len(title) > 100:
                    raise ValueError("标题须为 1 到 100 个字符")
                validated["title"] = title.strip()
            return validated

    def update(self, identifier, changes):
        from backend.scenes import public_scene
        with self.lock:
            validated = self.validate_update(identifier, changes)
            item = self.items[identifier]
            if "settings" in validated and identity_changed(item, validated["settings"]):
                item["identityEpoch"] = uid()
                item["scene"] = public_scene(item["roomId"], validated["settings"]["userRole"])
            item.update(validated)
            item["updatedAt"] = now()
            self._save()
            return copy.deepcopy(item)

    def set_scene(self, identifier, scene):
        from backend.scenes import public_scene
        with self.lock:
            item = self.items.get(identifier)
            if item is None:
                raise KeyError("会话不存在")
            role = normalized_identity(item["settings"], item["roomId"])["userRole"]
            allowed = set(public_scene(item["roomId"], role)["audience"])
            if not isinstance(scene, dict):
                raise ValueError("场景格式无效")
            audience = scene.get("audience")
            if not isinstance(audience, list) or not 2 <= len(audience) <= len(allowed) or any(not isinstance(p, str) for p in audience) or len(set(audience)) != len(audience) or not set(audience) <= allowed:
                raise ValueError("场景参与者无效")
            if scene.get("kind") not in ("public", "private"):
                raise ValueError("场景类型无效")
            if scene["kind"] == "public":
                scene = public_scene(item["roomId"], role)
            elif (not isinstance(scene.get("id"), str)
                  or not re.fullmatch(r"[a-f0-9]{32}", scene["id"])
                  or not isinstance(scene.get("label"), str) or not 1 <= len(scene["label"]) <= 200):
                raise ValueError("场景信息无效")
            item["scene"] = copy.deepcopy(scene)
            item["updatedAt"] = now()
            self._save()
            return copy.deepcopy(item)

    def append(self, identifier, message):
        with self.lock:
            self.get(identifier)
            item = self.items[identifier]
            from backend.scenes import current_scene
            scene = current_scene(item)
            epoch = identity_epoch(item)
            if "identityEpoch" in message and message["identityEpoch"] != epoch:
                raise ValueError("该消息属于已结束的身份上下文，不能加入当前对话。")
            message["identityEpoch"] = epoch
            message.setdefault("audience", scene["audience"])
            message.setdefault("scene", scene)
            if message["role"] == "user":
                message["actor"] = user_actor(item)
                if "user" not in scene["audience"] or message["actor"]["mode"] == "scene":
                    message["director"] = True
            if message["role"] == "user" and not any(m["role"] == "user" for m in item["messages"]):
                item["title"] = message["content"].replace("\n", " ").strip()[:28] or "图片消息"
            item["messages"].append(message)
            item["updatedAt"] = now()
            self._save()
            return copy.deepcopy(item)

    def update_message(self, identifier, message_id, changes):
        with self.lock:
            self.get(identifier)
            item = self.items[identifier]
            message = next((m for m in item["messages"] if m["id"] == message_id), None)
            if message is None:
                raise KeyError("消息不存在")
            if any(key in changes and changes[key] != message.get(key)
                   for key in ("identityEpoch", "actor", "role", "director")):
                raise ValueError("消息的身份归属不可修改。")
            message.update(changes)
            item["updatedAt"] = now()
            self._save()
            return copy.deepcopy(item)

    def delete(self, identifier):
        with self.lock:
            self.get(identifier)
            del self.items[identifier]
            self._save()


def make_message(role, content, **extra):
    return {"id": uid(), "role": role, "content": content, "createdAt": now(), **extra}
