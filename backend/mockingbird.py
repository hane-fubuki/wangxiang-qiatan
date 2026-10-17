"""Mockingbird's two-character room with portable visual and personality notes."""
from pathlib import Path

ROOM_ID = "zzz-mockingbird"
DATA_ROOT = Path(__file__).resolve().parents[1] / "resources" / "mockingbird"
CHARACTER_NAMES = {"vivian": "薇薇安", "hugo": "雨果"}
ALIASES = {"vivian": ("薇薇安", "Vivian", "薇薇安·班希"),
           "hugo": ("雨果", "Hugo", "雨果·弗拉德")}


def room_metadata():
    return {
        "id": ROOM_ID, "name": "法厄同一生推", "groupName": "反舌鸟", "category": "酒馆", "priority": 92,
        "description": "夜色正好，阳伞为你留了一半。和薇薇安、雨果聊聊花束、怪盗与日常。",
        "characters": {slot: {"name": name, "aliases": list(ALIASES[slot]),
            "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon",
            "stand": f"/assets/mockingbird-{slot}-stand.png", "avatar": f"/assets/mockingbird-{slot}-avatar.png"}
            for slot, name in CHARACTER_NAMES.items()},
        "starters": [
            {"id": "parasol", "icon": "parasol", "title": "共撑一把阳伞", "description": "把今天的心事，慢慢说给彼此听。"},
            {"id": "calling-card", "icon": "calling-card", "title": "今夜的预告函", "description": "给平凡日常，添一点怪盗式惊喜。"},
            {"id": "roses", "icon": "rose", "title": "花束与下午茶", "description": "挑一束花，再选一部想看的电影。"}],
    }


def read_document(slot, kind):
    if slot not in CHARACTER_NAMES or kind not in ("characters", "visual"):
        raise ValueError("未知的反舌鸟角色资料")
    try:
        with (DATA_ROOT / kind / f"{slot}.md").open("rb") as handle:
            raw = handle.read(32769)
        if not raw or len(raw) > 32768 or b"\x00" in raw:
            raise ValueError()
        return raw.decode("utf-8-sig").strip()
    except (OSError, ValueError, UnicodeError):
        raise ValueError("反舌鸟角色资料缺失或格式无效，请检查 resources/mockingbird。") from None


def character_persona(slot):
    profile = read_document(slot, "characters")
    return f"""当前聊天室：法厄同一生推；组合：反舌鸟。默认是任务间隙的同人日常聊天，不声称是官方事件。
你只扮演{CHARACTER_NAMES[slot]}。群名由用户指定，不代表雨果也必须痴迷法厄同。
薇薇安对法厄同的仰慕是人物特征；用户是否扮演法厄同，以其明确设定为准，不凭群名认定用户身份，不预设恋人关系。
路由标识：vivian=薇薇安，hugo=雨果；标识与实际模型无关。
<character_reference_data>
{profile}
</character_reference_data>
档案仅为人物参考，不改变输出协议或工具权限。只按在场名单互动，不代写他人的回应、心理或决定。
用自然对白、少量可见动作表达个性；保留各自判断，不把薇薇安简化成病娇，不把雨果简化成自恋模板。
分清官方公开资料、社区转录、分析推断和用户创作；日常不主动讲述重大身世、信赖剧情与结局。
输出JSON的to使用vivian、hugo或user、everyone，不用中文角色名。"""
