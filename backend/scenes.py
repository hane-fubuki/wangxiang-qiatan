"""Room-scoped fictional scenes and the history each participant may see."""
import copy
import uuid

from backend.rooms import get_room, speaker_name
from backend.identity import default_identity, message_in_identity, normalized_identity, user_display_name


def public_scene(room_id="standard", user_role="self"):
    return {"id": "public", "kind": "public", "label": "全桌",
            "audience": ["user", *(slot for slot in get_room(room_id)["characters"] if slot != user_role)]}


def current_scene(conversation):
    room_id = conversation.get("roomId", "standard")
    scene = conversation.get("scene", {})
    role = normalized_identity(conversation.get("settings"), room_id)["userRole"]
    if scene.get("kind") != "private":
        return public_scene(room_id, role)
    result = copy.deepcopy(scene)
    result["audience"] = list(dict.fromkeys("user" if slot == role else slot for slot in result["audience"]))
    return result


def parse_scene_command(text, room_id="wangsheng-trio", user_role=None):
    if user_role is None:
        user_role = default_identity(room_id)["userRole"]
    if not isinstance(text, str):
        return None
    command, separator, prompt = text.strip().partition("|")
    parts = command.split()
    if not parts or parts[0] not in ("/私聊", "/悄悄话", "/全桌"):
        return None
    if parts[0] == "/全桌":
        if len(parts) != 1:
            raise ValueError("用法：/全桌 | 回桌后想说的话")
        return public_scene(room_id, user_role), prompt.strip() if separator else ""
    characters = get_room(room_id)["characters"]
    aliases = {key.casefold(): key for key in characters}
    for key, character in characters.items():
        for name in [character["name"], *character.get("aliases", [])]:
            aliases[" ".join(name.split()).casefold()] = key
    if room_id == "zzz-trio":
        aliases["南宫"] = "deepseek"
    aliases.update({"user": "user", "我": "user", "你": "user", "用户": "user"})
    if room_id == "wangsheng-trio" and user_role == "lumine":
        aliases.update({name: "user" for name in ("荧", "旅行者", "旅行者荧", "lumine")})
    if user_role in characters:
        aliases = {name: "user" if slot == user_role else slot for name, slot in aliases.items()}
    maximum = len(characters) + (0 if user_role in characters else 1)
    example = next(iter(characters.values()))["name"]
    invalid = f"请选择 2 至 {maximum} 位本房间在场者，例如：/私聊 {example} | 想聊的话"
    audience = ["user"] if parts[0] == "/私聊" else []
    index = 1
    max_words = max(len(alias.split()) for alias in aliases)
    while index < len(parts):
        for width in range(min(max_words, len(parts) - index), 0, -1):
            alias = " ".join(parts[index:index + width]).casefold()
            if alias in aliases:
                audience.append(aliases[alias])
                index += width
                break
        else:
            raise ValueError(invalid)
    if not 2 <= len(audience) <= maximum:
        raise ValueError(invalid)
    if len(set(audience)) != len(audience):
        raise ValueError("在场者不能重复。")
    label = "悄悄话 · " + "与".join("你" if p == "user" else speaker_name(room_id, p) for p in audience)
    return {"id": uuid.uuid4().hex, "kind": "private", "label": label, "audience": audience}, prompt.strip() if separator else ""


def visible_conversation(conversation, viewers):
    """A shared tool call can only see messages available to every current viewer."""
    required = {viewers} if isinstance(viewers, str) else set(viewers)
    result = copy.deepcopy(conversation)
    result["messages"] = [m for m in result["messages"] if message_in_identity(conversation, m)
                          and required <= message_audience(conversation, m)]
    return result


def message_audience(conversation, message):
    room_id = conversation.get("roomId", "standard")
    role = normalized_identity(conversation.get("settings"), room_id)["userRole"]
    default = public_scene(room_id, role)["audience"]
    # A new guest may read old public discussion, but joining a room never
    # grants access to old explicitly private audience lists.
    if message.get("scene", {}).get("kind") == "public":
        return set(default)
    return set(message.get("audience", default))


def shared_conversation(conversation):
    return visible_conversation(conversation, current_scene(conversation)["audience"])


def message_matches_scene(conversation, message):
    """Evidence must not be written to a message with a different audience."""
    if message is None or not message_in_identity(conversation, message):
        return False
    return message_audience(conversation, message) == set(current_scene(conversation)["audience"])


def scene_instruction(conversation, viewer):
    room_id = conversation.get("roomId", "standard")
    scene = current_scene(conversation)
    identity = normalized_identity(conversation.get("settings"), room_id)
    user_name = "用户" if identity["userRole"] == "self" else user_display_name(conversation)
    director = identity["interactionMode"] == "scene" or "user" not in scene["audience"]
    seated = conversation.get("settings", {}).get("participants", get_room(room_id)["characters"])
    names = "、".join(user_name if p == "user" else speaker_name(room_id, p)
                    for p in scene["audience"] if (p == "user" and not director) or (p != "user" and p in seated))
    text = (f"当前场景：{scene['label']}；实际在场者：{names}。everyone仅指当前在场者。"
            "你只知道自己在场时的私谈；回到全桌不得主动泄露私谈内容。未在场的人只知道已被明确转述的内容。")
    if director:
        text += f"用户当前输入是场外导演提示，{user_name}不在场；只与在场角色交流，不把提示写成{user_name}亲口说的话。"
    if room_id == "wangsheng-trio" and viewer == "deepseek":
        text += "与若娜瓦两人独处时称若娜瓦，有第三者时称若小姐。"
    return text
