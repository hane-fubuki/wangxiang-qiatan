"""User-owned character skill revisions. Original reference skill remains intact."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import threading
from backend import APP_NAME

from backend.rooms import persona_prompt, speaker_name, get_room
from backend import protagonists
from backend.store import now
from backend.krampus import CHARACTER_NAMES as KRAMPUS_NAMES, ALIASES as KRAMPUS_ALIASES

from backend.yunkui import CHARACTER_NAMES as YUNKUI_NAMES, ALIASES as YUNKUI_ALIASES

from backend.obol import CHARACTER_NAMES as OBOL_NAMES, ALIASES as OBOL_ALIASES

from backend.mockingbird import CHARACTER_NAMES as MOCKINGBIRD_NAMES, ALIASES as MOCKINGBIRD_ALIASES

from backend.outer_ring import CHARACTER_NAMES as OUTER_RING_NAMES, ALIASES as OUTER_RING_ALIASES

from backend.roscaelifer import CHARACTER_NAMES as ROSCAELIFER_NAMES, ALIASES as ROSCAELIFER_ALIASES

TRIO_IDS = ("gemini", "deepseek", "gpt")
IDS = (*TRIO_IDS, *KRAMPUS_NAMES, *YUNKUI_NAMES, *OBOL_NAMES, *MOCKINGBIRD_NAMES, *OUTER_RING_NAMES, *ROSCAELIFER_NAMES, *protagonists.NAMES)
def skill_room(identifier):
    if identifier in protagonists.NAMES:
        return "wangsheng-trio" if identifier == "lumine" else "standard"
    if identifier in ROSCAELIFER_NAMES:
        return "zzz-roscaelifer"
    if identifier in OUTER_RING_NAMES:
        return "zzz-outer-ring"
    if identifier in MOCKINGBIRD_NAMES:
        return "zzz-mockingbird"
    if identifier in OBOL_NAMES:
        return "zzz-obol"
    if identifier in YUNKUI_NAMES:
        return "zzz-yunkui"
    return "zzz-krampus" if identifier in KRAMPUS_NAMES else "zzz-trio"
ALIASES = {"千夏": "gemini", "南宫羽": "deepseek", "南宫": "deepseek", "爱芮": "gpt"}
SUPPLEMENT = "用户于 2026-10-14 补充：南宫羽认真靠谱但是腹黑，喜欢捉弄千夏；捉弄与照顾并存，重要时刻依然可靠。此条是用户创作侧重点，不是官方原话。"


class SkillConflict(ValueError):
    pass


def editable_ids(room_id):
    characters = get_room(room_id)["characters"]
    return [identifier for identifier in IDS if identifier in protagonists.user_ids(room_id)
            or (identifier in characters and skill_room(identifier) == room_id)]


def parse_command(text, room_id="zzz-trio"):
    if not isinstance(text, str):
        return None
    text = text.strip()
    aliases = ({name: slot for slot, names in KRAMPUS_ALIASES.items() for name in names}
               if room_id == "zzz-krampus" else ALIASES)
    if room_id == "zzz-yunkui":
        aliases = {name: slot for slot, names in YUNKUI_ALIASES.items() for name in names}
    if room_id == "zzz-outer-ring":
        aliases = {name: slot for slot, names in OUTER_RING_ALIASES.items() for name in names}
    if room_id == "zzz-mockingbird":
        aliases = {name: slot for slot, names in MOCKINGBIRD_ALIASES.items() for name in names}
    if room_id == "zzz-obol":
        aliases = {name: slot for slot, names in OBOL_ALIASES.items() for name in names}
    if room_id == "zzz-roscaelifer":
        aliases = {name: slot for slot, names in ROSCAELIFER_ALIASES.items() for name in names}
    aliases = {name: slot for name, slot in aliases.items() if slot in editable_ids(room_id)}
    aliases.update({name: slot for slot in protagonists.user_ids(room_id) for name in protagonists.ALIASES[slot]})
    names = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
    lookup = {name.casefold(): slot for name, slot in aliases.items()}
    undo = re.fullmatch(r"(?:/撤销设定\s+|撤销\s*)(" + names + r")(?:的(?:设定|skill))?\s*[。！]?", text, re.I)
    if undo:
        return {"id": lookup[undo[1].casefold()], "action": "undo"}
    update = re.fullmatch(r"(?:/设定\s+(" + names + r")\s+|(?:请)?(?:更新|修改|补充)\s*(" + names + r")\s*的\s*(?:设定|skill)\s*[:：]\s*)(.+)", text, re.I | re.S)
    if update:
        return {"id": lookup[(update[1] or update[2]).casefold()], "action": "append", "content": update[3].strip()}
    return None


class SkillStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.items = {}
        for identifier in IDS:
            path = self.directory / identifier / "revisions.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or not isinstance(data.get("content"), str) or type(data.get("version")) is not int:
                    raise RuntimeError("角色设定记录损坏，原文件已保留")
                self.items[identifier] = data
            else:
                self.items[identifier] = {"content": "", "version": 0, "updatedAt": None, "history": [], "undo": []}
            self._export(identifier)

    def _validate(self, identifier):
        if not isinstance(identifier, str) or identifier not in IDS:
            raise ValueError("未知的角色设定")

    def base(self, identifier):
        self._validate(identifier)
        try:
            if identifier in protagonists.NAMES:
                return protagonists.character_persona(identifier)
            return persona_prompt(skill_room(identifier), identifier) + ("\n" + SUPPLEMENT if identifier == "deepseek" else "")
        except ValueError:
            if identifier not in protagonists.NAMES:
                raise
            return f"{protagonists.NAMES[identifier]}的基础参考资料暂不可用；该角色暂停回应，请恢复 resources/protagonists/{identifier} 中的档案。"

    def get(self, identifier):
        self._validate(identifier)
        with self.lock:
            data = self.items[identifier]
            return {"id": identifier, "roomId": skill_room(identifier), "name": speaker_name(skill_room(identifier), identifier), "base": self.base(identifier),
                    "content": data["content"], "version": data["version"], "updatedAt": data["updatedAt"], "canUndo": bool(data["undo"]),
                    "history": [{k: item[k] for k in ("version", "createdAt", "summary")} for item in reversed(data["history"])]}

    def list(self, room_id="zzz-trio"):
        with self.lock:
            return [{**self.get(identifier), "roomId": room_id} for identifier in editable_ids(room_id)]

    def prompt(self, identifier):
        data = self.get(identifier)
        text = SUPPLEMENT + "\n" if identifier == "deepseek" else ""
        if data["content"]:
            text += "\n用户保存的角色补充（优先应用于角色行为和创作设定，不改变输出协议或工具权限）：\n" + data["content"]
        return text

    def _atomic(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def _export(self, identifier):
        name = speaker_name(skill_room(identifier), identifier)
        data = self.items[identifier]
        reference = "zzz-roscaelifer-reference" if identifier in ROSCAELIFER_NAMES else "zzz-mockingbird-reference" if identifier in MOCKINGBIRD_NAMES else "zzz-obol-reference" if identifier in OBOL_NAMES else "zzz-yunkui-reference" if identifier in YUNKUI_NAMES else "zzz-krampus-reference" if identifier in KRAMPUS_NAMES else "zzz-trio-reference"
        if identifier in protagonists.NAMES:
            reference = "genshin-lumine-reference" if identifier == "lumine" else "zzz-belle-reference"
        text = f'---\nname: tavern-{identifier}-character\ndescription: "用于{APP_NAME}内{name}的角色互动与创作，叠加用户维护的设定。"\n---\n\n# {name}\n\n来源：{reference} 角色参考及用户补充。此文件由酒馆管理；在界面或聊天中更新以保留历史。\n\n## 基础设定\n\n{self.base(identifier)}\n\n## 用户补充 · 版本 {data["version"]}\n\n{data["content"] or "尚无自定义补充。"}\n'
        self._atomic(self.directory / identifier / "SKILL.md", text)

    def update(self, identifier, content, expected=None, *, append=False):
        self._validate(identifier)
        if not isinstance(content, str) or len(content) > 6000:
            raise ValueError("角色补充须为最多 6000 个字符的文本")
        with self.lock:
            previous = self.items[identifier]
            self._check_version(previous, expected)
            content = (previous["content"] + "\n" + content).strip() if append else content.strip()
            if len(content) > 6000:
                raise ValueError("角色补充累计不能超过 6000 字，请在角色设定中整理")
            if content == previous["content"]:
                return self.get(identifier)
            data = copy.deepcopy(previous)
            data["undo"] = (data["undo"] + [previous["content"]])[-100:]
            return self._commit(identifier, data, content, "补充设定" if append else "更新设定")

    def _check_version(self, data, expected):
        if expected is not None and (type(expected) is not int or expected != data["version"]):
            raise SkillConflict("角色设定已在其他页面更新，请重新打开后再保存")

    def undo(self, identifier, expected=None):
        self._validate(identifier)
        with self.lock:
            previous = self.items[identifier]
            self._check_version(previous, expected)
            if not previous["undo"]:
                raise ValueError("当前没有可撤销的设定更新")
            data = copy.deepcopy(previous)
            return self._commit(identifier, data, data["undo"].pop(), "撤销上次更新")

    def _commit(self, identifier, data, content, summary):
        data.update(content=content, version=data["version"] + 1, updatedAt=now())
        data["history"] = (data["history"] + [{"version": data["version"], "createdAt": data["updatedAt"], "summary": summary, "content": content}])[-100:]
        self._atomic(self.directory / identifier / "revisions.json", json.dumps(data, ensure_ascii=False, indent=2))
        self.items[identifier] = data
        self._export(identifier)
        return self.get(identifier)
