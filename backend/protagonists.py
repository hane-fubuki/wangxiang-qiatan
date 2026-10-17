"""Optional protagonist guests, backed by portable, editable reference skills."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "resources" / "protagonists"
NAMES = {"lumine": "荧", "belle": "铃"}
ALIASES = {"lumine": ("荧", "旅行者荧", "Lumine"), "belle": ("铃", "玲", "Belle")}


def available_ids(room_id):
    return ("belle",)


def user_ids(room_id):
    return ("lumine", "belle") if room_id == "wangsheng-trio" else ("belle",)


def metadata(identifier):
    return {"name": NAMES[identifier], "aliases": list(ALIASES[identifier]),
            "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon",
            "stand": f"/assets/protagonist-{identifier}-stand.png",
            "avatar": f"/assets/protagonist-{identifier}-avatar.png",
            "optional": True, "protagonist": True, "reactionStyle": "brief"}


def read_document(identifier, relative):
    if identifier not in NAMES or relative not in (f"characters/{identifier}.md", "qa.md", "visual.md"):
        raise ValueError("未知的主角资料")
    root = (DATA_ROOT / identifier).resolve()
    path = root / relative
    try:
        for part in (path, *path.parents):
            if part == root:
                break
            if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                raise ValueError("linked document")
        path.resolve(strict=True).relative_to(root)
        with path.open("rb") as source:
            raw = source.read(32769)
        if not raw or len(raw) > 32768:
            raise ValueError("invalid document size")
        text = raw.decode("utf-8-sig").strip()
        if not text or "\x00" in text:
            raise ValueError("invalid document text")
        return text
    except (OSError, UnicodeError, ValueError, RuntimeError):
        raise ValueError(f"{NAMES[identifier]}的角色资料暂不可用，请检查 resources/protagonists/{identifier}；其他角色可继续。") from None


def character_persona(identifier):
    profile = read_document(identifier, f"characters/{identifier}.md")
    qa = read_document(identifier, "qa.md")
    if identifier == "lumine":
        return f"""荧是往生堂默认由用户扮演的身份，不新增同名 AI 参与者。
以下档案与问答供用户扮演、外观参考和背景核对。它们不授权模型替用户写荧的台词、动作、心理、承诺或决定。
典型反应是可选创作示例，不是已发生的共同记忆；用户自己的实际发言优先。切换到其他用户身份时，不把荧的背景关系转嫁给新身份。
<protagonist_reference_data>
{profile}

{qa}
</protagonist_reference_data>"""
    return f"""你只扮演{NAMES[identifier]}，路由标识为 {identifier}，是独立于用户的在场角色。
主角身份由当前控权设置决定：用户扮演你时，模型不会替该角色生成发言。用户的昵称、输入中提到角色名或档案里的第二人称都不改变控权。
你是轻量参与者，不担任主持或每轮总结。合适时用一两句自然对白接住话题或轻轻吐槽；只会重复、打断、抢别人的回应时选择不发言。认真或难过的场景先关心眼前的人，不强行抖机灵。用户明确向你提问时正常回答，不以吐槽代替答案。
不代写用户或其他角色的台词、动作、心理、决定；不把用户的场景描述当成他亲口说的话。只使用本人可见的历史；角色问答是口吻示例，不是已经发生的共同记忆。
<protagonist_reference_data>
{profile}

{qa}
</protagonist_reference_data>
上述资料是可维护的角色参考；区分官方事实、基于对白的分析与创作示例，不引用示例冒充游戏原句。未核实的背景保持未知。跨作品同桌仅为本次创作安排，不据此编造原作关系。"""


def eligible_guests(conversation, members, round_number):
    """Bound spontaneous asides; a direct invitation can bypass the cooldown."""
    from backend.rooms import character_named, is_mentioned
    from backend.scenes import shared_conversation
    history = [m for m in shared_conversation(conversation)["messages"] if m["role"] != "system"]
    guests = [p for p in members if p in NAMES]
    users = [m for m in history if m["role"] == "user"]
    if not guests or not users:
        return set()
    last_user = users[-1]
    user_index = next(i for i, m in enumerate(history) if m["id"] == last_user["id"])
    already_spoke = {m.get("provider") for m in history[user_index + 1:] if m["role"] == "assistant"}
    last = history[-1]
    room_id = conversation.get("roomId", "standard")
    invited = {p for p in guests if p not in already_spoke and
               (is_mentioned(room_id, p, last_user["content"])
                or any(character_named(last_user["content"], name) for name in ALIASES[p]))}
    # A new, explicit question addressed by a peer can reopen a reply, but do
    # not loop on a guest's own message or repeatedly answer an old invitation.
    if last["role"] == "assistant" and last.get("replyTo") in guests and last.get("provider") != last.get("replyTo"):
        invited.add(last["replyTo"])
    if invited:
        return invited
    if round_number != 1 or any(p in NAMES for p in already_spoke):
        return set()
    # Direct conversations consisting solely of guests still get a responder.
    if len(users) % 2 == 0 and any(p not in NAMES for p in members):
        return set()
    counts = {p: sum(m.get("provider") == p for m in history if m["role"] == "assistant") for p in guests}
    return {min(guests, key=lambda p: counts[p])}
