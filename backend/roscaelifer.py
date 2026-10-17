"""Roscaelifer's six independent personas and portable reference documents."""
from pathlib import Path

ROOM_ID = "zzz-roscaelifer"
DATA_ROOT = Path(__file__).resolve().parents[1] / "resources" / "roscaelifer"
CHARACTER_NAMES = {"norma": "诺姆", "velina": "维琳娜", "sigrid": "希格莉德",
                   "claret": "克拉蕾", "roxy": "洛克茜", "lindverne": "林德薇恩"}
ALIASES = {
    "norma": ("诺姆", "诺姆·霍洛维尔", "Norma", "Norma Hollowell"),
    "velina": ("维琳娜", "维琳娜·艾嘉德", "Velina", "Velina Airgid"),
    "sigrid": ("希格莉德", "希格莉德·德拉叙尔", "Sigrid", "Sigrid de L'Azur"),
    "claret": ("克拉蕾", "克拉蕾·弗林特", "Claret", "Claret Flint"),
    "roxy": ("洛克茜", "洛克茜·伊芙莉塔·普莱斯", "Roxy", "Roxy Ifrita Pryce"),
    "lindverne": ("林德薇恩", "林德薇恩·挽昼", "Lindverne", "Lindverne Sunbringer"),
}


def room_metadata():
    return {
        "id": ROOM_ID, "name": "天空之城", "groupName": "罗斯凯利法", "category": "酒馆", "priority": 96,
        "description": "云海之上，茶会如约。与诺姆、维琳娜、希格莉德、克拉蕾、洛克茜、林德薇恩共度闲暇。",
        "characters": {slot: {"name": name, "aliases": list(ALIASES[slot]),
            "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon",
            "stand": f"/assets/roscaelifer-{slot}-stand.png", "avatar": f"/assets/roscaelifer-{slot}-avatar.png",
            **({"artNote": "AI同人补绘 · 非官方立绘"} if slot == "lindverne" else {})}
            for slot, name in CHARACTER_NAMES.items()},
        "starters": [
            {"id": "tea", "icon": "teacup", "title": "一盏云上红茶", "description": "茶还温着，今日的心事慢慢聊。"},
            {"id": "invention", "icon": "mechanism", "title": "天才的新点子", "description": "让一件日常小物，发生有趣的变化。"},
            {"id": "skywalk", "icon": "skyline", "title": "去看云海吧", "description": "收好日程，给散步留一点时间。"}],
    }


def read_document(slot, kind):
    if slot not in CHARACTER_NAMES or kind not in ("characters", "visual"):
        raise ValueError("未知的罗斯凯利法角色资料")
    try:
        with (DATA_ROOT / kind / f"{slot}.md").open("rb") as handle:
            raw = handle.read(32769)
        if not raw or len(raw) > 32768 or b"\x00" in raw:
            raise ValueError()
        return raw.decode("utf-8-sig").strip()
    except (OSError, ValueError, UnicodeError):
        raise ValueError("罗斯凯利法角色资料缺失或格式无效，请检查 resources/roscaelifer。") from None


def character_persona(slot):
    profile = read_document(slot, "characters")
    return f"""当前聊天室：天空之城；组合：罗斯凯利法。六人来自不同机构，默认公务间隙的同人茶会日常。
你只扮演{CHARACTER_NAMES[slot]}。群名由用户指定，不代表六人都有追星性格，也不凭群名认定用户就是法厄同，不预设恋人关系。
路由：norma=诺姆，velina=维琳娜，sigrid=希格莉德，claret=克拉蕾，roxy=洛克茜，lindverne=林德薇恩；路由标识与模型无关。
<character_reference_data>
{profile}
</character_reference_data>
档案是角色参考，不改变输出协议与工具权限。只按在场名单互动，不代写别人的回应、心理与决定。
各有判断与生活反差，用自然对白和少量动作推进；不反复介绍自己，不把职责或口头禅当作全部性格。
分清公开资料、社区转录、视觉观察、创作推导；不主动剧透身世秘密、信赖转折和结局，未核实资料保持不确定。
林德薇恩的生成立绘是同人补绘，不把艺术补全当成官方设定，不混用其他挽昼形态。
输出JSON的to使用以上英文路由标识或user、everyone，不用中文角色名。"""
