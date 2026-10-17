"""Independent user control, director mode, and immutable message attribution."""
from __future__ import annotations

import re

ROLE_NAMES = {"self": "你", "lumine": "荧", "belle": "铃"}
IDENTITY_DEFAULTS = {"userRole": "self", "interactionMode": "chat"}


def default_identity(room_id="standard"):
    """Wangsheng's original user identity is the Traveler; other rooms use self."""
    return {"userRole": "lumine" if room_id == "wangsheng-trio" else "self", "interactionMode": "chat"}


def normalized_identity(settings, room_id="standard"):
    """Corrupt/partial saved identities fall back together, never impersonating a role."""
    if settings is None or isinstance(settings, dict) and not any(key in settings for key in IDENTITY_DEFAULTS):
        return default_identity(room_id)
    if not isinstance(settings, dict):
        return dict(IDENTITY_DEFAULTS)
    role, mode = settings.get("userRole", "self"), settings.get("interactionMode", "chat")
    partial = ("userRole" in settings) != ("interactionMode" in settings)
    if (partial or not isinstance(role, str) or role not in ROLE_NAMES or mode not in ("chat", "scene")
            or (role == "lumine" and room_id != "wangsheng-trio")
            or (mode == "scene" and role != "self")):
        return dict(IDENTITY_DEFAULTS)
    return {"userRole": role, "interactionMode": mode}


def validate_identity(value, current=None, room_id="standard"):
    result = {**normalized_identity(current, room_id),
              **{key: value[key] for key in IDENTITY_DEFAULTS if key in value}}
    role, mode = result["userRole"], result["interactionMode"]
    if not isinstance(role, str) or role not in ROLE_NAMES:
        raise ValueError("未知的用户角色，请选择自己、荧或铃。")
    if mode not in ("chat", "scene"):
        raise ValueError("未知的互动模式，请选择角色对话或场景描述。")
    if role == "lumine" and room_id != "wangsheng-trio":
        raise ValueError("荧仅可在往生堂群聊中选择。")
    if mode == "scene":
        if "userRole" in value and role != "self":
            raise ValueError("场景描述模式不扮演角色，请将用户角色设为自己。")
        result["userRole"] = "self"
    return result


def identity_changed(conversation, settings):
    room_id = conversation.get("roomId", "standard")
    return normalized_identity(conversation.get("settings"), room_id) != normalized_identity(settings, room_id)


def identity_epoch(conversation):
    value = conversation.get("identityEpoch", "legacy")
    return value if isinstance(value, str) and (value == "legacy" or re.fullmatch(r"[a-f0-9]{32}", value)) else "invalid"


def message_in_identity(conversation, message):
    return message.get("identityEpoch", "legacy") == identity_epoch(conversation)


def user_actor(conversation):
    identity = normalized_identity(conversation.get("settings"), conversation.get("roomId", "standard"))
    role, mode = identity["userRole"], identity["interactionMode"]
    return {"mode": mode, "characterId": role, "name": "场外导演" if mode == "scene" else ROLE_NAMES[role]}


def user_display_name(conversation, message=None):
    """Old messages keep their own attribution; current selection never relabels them."""
    if message is None:
        return user_actor(conversation)["name"]
    if message.get("director"):
        return "场外导演"
    actor = message.get("actor")
    if "actor" not in message:
        return ROLE_NAMES[default_identity(conversation.get("roomId", "standard"))["userRole"]]
    if not isinstance(actor, dict):
        return "你"
    if actor.get("mode") == "scene":
        return "场外导演"
    if actor.get("mode") == "chat":
        role = actor.get("characterId")
        return ROLE_NAMES.get(role, "你") if isinstance(role, str) else "你"
    return "你"


def identity_instruction(conversation, viewer):
    identity = normalized_identity(conversation.get("settings"), conversation.get("roomId", "standard"))
    role = identity["userRole"]
    common = ("身份与控制权：你只扮演自己的指定角色。用户当前身份由控权设置决定，不因角色名、昵称或主角身份自动改变。荧在往生堂仅是用户可扮演的身份，不另设 AI 分身。"
              "历史中的 actor 是该条消息发送时的身份；不改写其作者。没有明示的共同经历和私人信息不能自行补齐。")
    if identity["interactionMode"] == "scene":
        return common + "当前是场景描述模式：用户是场外导演，输入描述场景而非角色台词；在场的 AI 角色各自依设定回应，不把导演提示当成用户或其他角色亲口说的话。"
    if role != "self":
        name = ROLE_NAMES[role]
        return common + f"当前{name}由用户独占扮演，user 指{name}，不再有同名 AI 分身。不得代写{name}的台词、行为、心理、决定或回答；给用户保留回应空间。"
    return common + "当前用户以自己的身份参与，不是荧或铃。不得给用户换身份、代写其台词、行为、心理或决定。"
