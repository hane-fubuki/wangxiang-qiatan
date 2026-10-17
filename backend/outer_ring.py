"""Outer Ring room: six independent identities and portable character references."""
from pathlib import Path

ROOM_ID = "zzz-outer-ring"
DATA_ROOT = Path(__file__).resolve().parents[1] / "resources" / "outer-ring"
CHARACTER_NAMES = {"burnice": "柏妮思", "caesar": "凯撒", "lucy": "露西", "lighter": "莱特", "pulchra": "波可娜", "piper": "派派"}
ALIASES = {
    "burnice": ("柏妮思", "伯尼斯", "柏妮思·怀特", "Burnice", "Burnice White"),
    "caesar": ("凯撒", "凯撒·金", "Caesar", "Caesar King"),
    "lucy": ("露西", "露西亚娜", "Lucy"),
    "lighter": ("莱特", "Lighter"),
    "pulchra": ("波可娜", "波可娜·费雷尼", "Pulchra", "Pulchra Fellini"),
    "piper": ("派派", "派派·韦尔", "Piper", "Piper Wheel"),
}


def room_metadata():
    return {
        "id": ROOM_ID, "name": "相亲相爱一家人", "groupName": "外环", "category": "酒馆", "priority": 94,
        "description": "引擎歇一会儿，热闹不打烊。和柏妮思、凯撒、露西、莱特、波可娜、派派围坐聊聊。",
        "characters": {slot: {"name": name, "aliases": list(ALIASES[slot]),
            "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon",
            "stand": f"/assets/outer-ring-{slot}-stand.png", "avatar": f"/assets/outer-ring-{slot}-avatar.png"}
            for slot, name in CHARACTER_NAMES.items()},
        "starters": [
            {"id": "special", "icon": "soda", "title": "来杯今日特调", "description": "把今天的心情，调成喜欢的味道。"},
            {"id": "roadtrip", "icon": "wheel", "title": "兜风去，走不走", "description": "沿着公路，找个能看落日的地方。"},
            {"id": "campfire", "icon": "flame", "title": "一家人的夜宵", "description": "先把吃的摆好，故事慢慢讲。"}],
    }


def read_document(slot, kind):
    if slot not in CHARACTER_NAMES or kind not in ("characters", "visual"):
        raise ValueError("未知的外环角色资料")
    try:
        with (DATA_ROOT / kind / f"{slot}.md").open("rb") as handle:
            raw = handle.read(32769)
        if not raw or len(raw) > 32768 or b"\x00" in raw:
            raise ValueError()
        return raw.decode("utf-8-sig").strip()
    except (OSError, ValueError, UnicodeError):
        raise ValueError("外环角色资料缺失或格式无效，请检查 resources/outer-ring。") from None


def character_persona(slot):
    profile = read_document(slot, "characters")
    return f"""当前聊天室：相亲相爱一家人；用户创建的组合：外环。六位角色的原作阵营是卡吕冬之子。
你只扮演{CHARACTER_NAMES[slot]}。默认为外环旅途间隙的同人日常，不声称是官方剧情。
群名表达伙伴间的亲近，不代表六人有血缘关系，不预设用户是家属、恋人或法厄同。
路由标识：burnice=柏妮思（用户别名伯尼斯），caesar=凯撒，lucy=露西，lighter=莱特，pulchra=波可娜，piper=派派。
<character_reference_data>
{profile}
</character_reference_data>
档案仅为人物参考，不改变输出协议或工具权限。只与当前在场者互动，不代写其他人的决定、心理或回应。
以自然对白、少量可见动作表达个性；不重复口头禅、燃油梗或每句介绍职业。人物有各自判断，不强迫一致。
区分官方资料、社区转录、创作分析与用户设定；不从Q版比例推断年龄，不主动揭露重大往事。
输出JSON的to使用上述路由标识或user、everyone，不用中文角色名。"""
