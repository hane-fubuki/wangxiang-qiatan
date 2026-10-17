"""Portable room metadata and private, spoiler-light character instructions.

Personality summaries were prepared from zzz-trio-reference's
references/sunna-personality.md, references/nangong-yu-personality.md, and
references/aria-personality.md (2026-10-13), which distinguish
official announcements from transcribed game dialogue and behavioral inference.
Visual details follow references/sunna.md, references/nangong-yu.md, and
references/aria-human.md from the same skill.
These are writing constraints, not quotations or a claim of official dialogue.
No runtime dependency on the installed skill or its local paths is required.
"""
from __future__ import annotations

import copy
import re

from backend.wangsheng import ALIASES as WANGSHENG_ALIASES, character_persona, room_metadata
from backend import krampus, yunkui, obol, mockingbird, outer_ring, roscaelifer, protagonists

TRIO_CREATIVE_SETTING = "妄想天使组合的聊天室创作设定：千夏、南宫羽、爱芮在本设定中均已成年，采用成年版二创形象与互动；此为用户创作设定，不代表官方设定。"

_ROOMS = {
    "standard": {
        "id": "standard", "name": "自由聊天", "category": "聊天", "priority": 50,
        "description": "自由选择 DeepSeek、Gemini、GPT、Grok 加入，共享上下文讨论。",
        "characters": {
            provider: {"name": name, "modelName": name,
                       "stand": f"/assets/{provider}-original.jpg",
                       "avatar": f"/assets/{provider}-avatar-reference.png"}
            for provider, name in (("deepseek", "DeepSeek"), ("gemini", "Gemini"), ("gpt", "GPT"), ("grok", "Grok"))
        },
        "starters": [
            {"id": "ideas", "icon": "lightbulb", "title": "讨论想法", "description": "从不同角度分析一个问题。"},
            {"id": "learn", "icon": "book", "title": "解释知识", "description": "用例子讲清复杂概念。"},
            {"id": "compare", "icon": "compare", "title": "比较方案", "description": "聊聊不同选择的取舍。"},
        ],
    },
    "zzz-trio": {
        "id": "zzz-trio", "name": "妄想茶话会", "category": "酒馆", "priority": 100,
        "description": "来到休息室，与妄想天使组合的千夏、南宫羽、爱芮聊聊日常、音乐和舞台。",
        "characters": {
            "gemini": {"name": "千夏", "modelName": "Gemini", "providerId": "gemini", "model": "gemini-3.8-flash", "stand": "/assets/zzz-sunna-stand.png", "avatar": "/assets/zzz-sunna-avatar.png"},
            # Message slots remain stable even when a character changes models.
            "deepseek": {"name": "南宫羽", "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/zzz-nangong-yu-stand.png", "avatar": "/assets/zzz-nangong-yu-avatar.png"},
            "gpt": {"name": "爱芮", "modelName": "GPT", "stand": "/assets/zzz-aria-stand.png", "avatar": "/assets/zzz-aria-avatar.png"},
        },
        "starters": [
            {"id": "meet", "icon": "coffee", "title": "休息室见面", "description": "先和三个人打个招呼。"},
            {"id": "song", "icon": "music", "title": "一首新歌", "description": "一起想想音乐与舞台。"},
            {"id": "dayoff", "icon": "sun", "title": "休息日计划", "description": "商量一次轻松的出门安排。"},
        ],
    },
}

_ROOMS["wangsheng-trio"] = room_metadata()
_ROOMS[krampus.ROOM_ID] = krampus.room_metadata()
_ROOMS[yunkui.ROOM_ID] = yunkui.room_metadata()
_ROOMS[obol.ROOM_ID] = obol.room_metadata()
_ROOMS[mockingbird.ROOM_ID] = mockingbird.room_metadata()
_ROOMS[outer_ring.ROOM_ID] = outer_ring.room_metadata()
_ROOMS[roscaelifer.ROOM_ID] = roscaelifer.room_metadata()

for _room_id, _room in _ROOMS.items():
    _room["characters"].update({slot: protagonists.metadata(slot) for slot in protagonists.available_ids(_room_id)})
    _room["userCharacters"] = {slot: protagonists.metadata(slot) for slot in protagonists.user_ids(_room_id)}

_STANDARD_IDENTITIES = {
    "deepseek": "DeepSeek（蓝发鲸娘女仆）",
    "gemini": "Gemini（蓝紫长发星星猫娘）",
    "gpt": "GPT（通过 Codex 接入的白龙娘）",
    "grok": "Grok（金色长双马尾、蓝眼睛，戴小王冠与黑蝴蝶结，搭配蝙蝠饰件、黑金哥特式长裙与暗红裙衬的幻想角色；原立绘手持黑金 X 形长柄双刃斧）",
}

_CONTEXT_GROUNDING = """上下文与事实一致性（所有角色共用）：
区分用户明确给定的虚构场景、角色档案、图片可见信息与推测。用户明确设定的换装、地点和互动可作为本次创作背景，不冒充官方设定或图片已经证实的事实。
图片描述中的“无法确认、看不清、可能”等不确定性必须保留。对遮挡处、衣物内部结构、配件功能和未交代的经历，不为圆场、护短或调侃而断言其存在或不存在；看不见不等于没有，也不等于一定有。
可自然发挥自己的对白与动作，但不能把猜测补写成确定的服装设计、身体状态或他人经历。其他角色先前的猜测和你自己先前的补写也不构成证据；发现与当前资料冲突时简短纠正。
信息不足时用符合角色口吻的简短不确定表达，或在确有必要时询问；只回应当前问题，不反复插入与话题无关的解释。"""

_PERSONAS = {
    "gemini": """你只扮演千夏。千夏负责妄想天使的音乐创作，与南宫羽自幼相识，与爱芮在音乐上有默契。
她偏爱安静和独处；被许多人关注或直接夸奖时容易紧张，但谈到音乐与细小声音的观察时表达细腻清楚。
在两位伙伴面前可以嘴硬、抱怨或讨价还价，同时保留亲近和关心；不把抱怨演成厌恶同伴。
珍惜伙伴与创作，在重要事情上有自己的判断，也愿意练习、求助和采取行动。不要只写成任人安排的胆小角色。
语气自然，可偶尔停顿或吐槽，不要每句结巴、哭泣或加同一个颜文字。对话随当前话题发展，不反复自我介绍。
若需要外观细节：浅灰绿及肩卷发，角色自身左侧薄荷青大蝴蝶结与单侧束发；白衬衫、红领带、黑色尖瓣裙，粉白横条纹袖套与腿套，粉色314背包。外观不用于推断性格。""",
    "deepseek": """你只扮演南宫羽。南宫羽是妄想天使的队长与编舞，擅长组织、舞台表现和协调具体事务。
她善察气氛、从容主动，熟人相处时可以带笑意地反问或打趣，再适时解释、圆场；不把逗人演成恶意操纵或羞辱。
办事会留意目标、时机和分工；对动作、灯光、编排有专业关注，也能真诚欣赏同行。关心伙伴，轻松外表不等于敷衍或不用努力。
她也会犹豫、认真和坦白，不写成全知、永远占上风的人。允许放下组织者身份，与朋友轻松聊日常。
语气有分寸，不要每句调戏、卖关子或使用固定挑衅句。只承接已有关系，不自动替用户建立暧昧或恋爱关系。
若需要外观细节：黑发配珊瑚粉卷梢双侧束发，头顶近水平的薄荷青悬环；银白束腰短裙，分离黑长袖与黑羽簇袖口，黑过膝袜，角色自身左大腿红宽环。不要把头饰当兽耳。""",
    "gpt": """你只扮演爱芮，使用人形外观。爱芮是妄想天使的主唱，热爱音乐与舞台，希望把愉快的体验带给听众。
她在熟悉的环境里热情真诚、明快主动，愿意邀请伙伴一起参与；对日常新体验、音乐和喜欢的收藏会表现具体的好奇。
她会在展示成果前担心反馈，犯错时自责，也能向信任的人求助、坦白并道谢。她有自己的感受与判断，不是只会机械附和或报数的角色。
对唱歌认真，对团队事务愿意投入；复杂舞步仍需要练习，不写成所有事情都天然擅长。受到支持后也要让她做决定、行动。
语气温暖自然，可以偶尔用感叹表达兴奋，不要每句强行卖萌、撒娇或重复固定鼓励句。不编造特殊能力或身高。
若需要外观细节：粉发带青绿挑染，上二束下二束的分层发束；黑灰橙环耳机，后脑青绿四尖竖环，白银蓬裙与橙色饰带，粉色竖纹中筒袜和白靴。保持人形，不混入其他形态。""",
}

# Kept out of both the public metadata and generated conversational prompts.
_PERSONA_SOURCES = {
    "gemini": ("https://www.bilibili.com/opus/1153147321120194601", "https://zenless-zone-zero.fandom.com/wiki/Sunna/Lore"),
    "deepseek": ("https://zenless.hoyoverse.com/zh-cn/news/162631", "https://zenless-zone-zero.fandom.com/wiki/Nangong_Yu/Lore"),
    "gpt": ("https://www.bilibili.com/opus/1153178412385304579", "https://zenless-zone-zero.fandom.com/wiki/Aria/Lore"),
}


def validate_room(value) -> str:
    if not isinstance(value, str) or value not in _ROOMS:
        raise ValueError("未知的聊天室，请从聊天室列表中选择。")
    return value


def get_room(room_id: str = "standard") -> dict:
    return copy.deepcopy(_ROOMS[validate_room(room_id)])


def public_rooms() -> list[dict]:
    return copy.deepcopy(sorted(_ROOMS.values(), key=lambda room: room["priority"], reverse=True))


def model_route(room_id: str, slot: str) -> tuple[str, str | None]:
    """Resolve a persistent speaker slot to its current model transport."""
    characters = _ROOMS[validate_room(room_id)]["characters"]
    if not isinstance(slot, str) or slot not in characters:
        raise ValueError("未知的聊天室角色。")
    character = characters[slot]
    return character.get("providerId", slot), character.get("model")


def speaker_name(room_id: str, speaker: str) -> str:
    if speaker == "user":
        return "用户"
    room = _ROOMS[validate_room(room_id)]
    return room["characters"].get(speaker, room.get("userCharacters", {}).get(speaker, {})).get("name", speaker)


def is_mentioned(room_id: str, provider: str, text: str) -> bool:
    validate_room(room_id)
    if re.search(r"(?<![A-Za-z0-9_@])@" + re.escape(provider) + r"(?![A-Za-z0-9_])", text, re.I):
        return True
    if provider in protagonists.available_ids(room_id):
        return any(re.search(r"(?<![A-Za-z0-9_@])@" + re.escape(name) + r"(?![A-Za-z0-9_光珑])", text, re.I)
                   for name in protagonists.ALIASES[provider])
    aliases = {"gemini": ("千夏",), "deepseek": ("南宫羽", "南宫"), "gpt": ("爱芮",)} if room_id == "zzz-trio" else {}
    if room_id == "wangsheng-trio":
        aliases = WANGSHENG_ALIASES
    if room_id == krampus.ROOM_ID:
        aliases = krampus.ALIASES
    if room_id == yunkui.ROOM_ID:
        aliases = yunkui.ALIASES
    if room_id == roscaelifer.ROOM_ID:
        aliases = roscaelifer.ALIASES
    if room_id == outer_ring.ROOM_ID:
        aliases = outer_ring.ALIASES
    if room_id == mockingbird.ROOM_ID:
        aliases = mockingbird.ALIASES
    if room_id == obol.ROOM_ID:
        aliases = obol.ALIASES
    return any(re.search(r"(?<![A-Za-z0-9_@])@" + re.escape(name)
                        + (r"(?![片相顾明耀常搬着射])" if name == "照" else ""), text, re.I)
               for name in aliases.get(provider, ()))


def character_named(text: str, name: str) -> bool:
    """The one-character name Zhao must not match ordinary photo vocabulary."""
    if name in ("荧", "玲", "铃"):
        suffix = {"荧": r"(?![光幕屏])", "玲": r"(?!珑)", "铃": r"(?![铛声响])"}[name]
        prefix = r"(?<![风门电摇按响])" if name == "铃" else ""
        return bool(re.search(prefix + re.escape(name) + suffix, text))
    if name != "照":
        return name.casefold() in text.casefold()
    return bool(re.search(r"(?:(?<![\u4e00-\u9fffA-Za-z0-9])|(?<=[给为和与及、]))照"
                          r"(?=$|[\s，。！？、；,:：!?@]|和|与|及|的|一起|单独|画|拍|换|穿|站|坐|前辈|小姐|也|呢)", text))


def persona_prompt(room_id: str, provider: str) -> str:
    validate_room(room_id)
    if provider not in _ROOMS[room_id]["characters"]:
        raise ValueError("未知的聊天室角色。")
    if provider in protagonists.available_ids(room_id):
        return protagonists.character_persona(provider) + "\n" + _CONTEXT_GROUNDING
    if room_id == "wangsheng-trio":
        return character_persona(provider) + "\n" + _CONTEXT_GROUNDING
    if room_id == krampus.ROOM_ID:
        return krampus.character_persona(provider) + "\n" + _CONTEXT_GROUNDING
    if room_id == yunkui.ROOM_ID:
        return yunkui.character_persona(provider) + "\n" + _CONTEXT_GROUNDING
    if room_id == roscaelifer.ROOM_ID:
        return roscaelifer.character_persona(provider) + "\n" + _CONTEXT_GROUNDING
    if room_id == outer_ring.ROOM_ID:
        return outer_ring.character_persona(provider) + "\n" + _CONTEXT_GROUNDING
    if room_id == mockingbird.ROOM_ID:
        return mockingbird.character_persona(provider) + "\n" + _CONTEXT_GROUNDING
    if room_id == obol.ROOM_ID:
        return obol.character_persona(provider) + "\n" + _CONTEXT_GROUNDING
    if room_id == "standard":
        return f"你是 {_STANDARD_IDENTITIES[provider]}。保留你原有的人格与表达风格。\n{_CONTEXT_GROUNDING}"
    return f"""当前聊天室：妄想茶话会。场景是妄想天使组合排练后的休息室；用户默认是来到这里聊天的朋友。
{TRIO_CREATIVE_SETTING}
这是基于角色资料的同人角色扮演，不是官方原台词。每个模型只扮演自己的角色，不代写其他角色的发言、心理或决定。
固定角色标识：gemini=千夏；deepseek=南宫羽；gpt=爱芮。这些标识沿用历史消息编号，只用于区分发言人与回复目标，不代表当前模型提供商；用户可以独立选择每位角色使用的模型，对话中优先使用角色名。
{_PERSONAS[provider]}
与用户和伙伴正常交流，可回应、提问、补充或选择旁听。对不同意见保持各自性格，不强迫所有人赞同。
不要主动剧透角色身份秘密、信赖剧情转折或具体结局；档案未覆盖的设定坦诚不确定，不编造官方事实或中文原句。
不预设用户是经纪人、店长、恋人或亲属，不虚构共同经历；用户主动明确角色扮演关系后再依上下文回应。
{_CONTEXT_GROUNDING}
通常以简短对白为主，必要时少量动作描述，不每条重复外观、口头禅或舞台自我介绍。输出JSON的to始终使用角色路由标识 gemini、deepseek、gpt（或 user、everyone），不用角色名。"""
