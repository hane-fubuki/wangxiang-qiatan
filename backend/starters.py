"""Bounded model-generated conversation starters, isolated from chat history."""
from __future__ import annotations

from collections import deque
import json
import random
import re
import threading
import time
import unicodedata

from backend.engine import parse_decision
from backend.providers import GatewayError
from backend.rooms import get_room


_PROVIDER_ORDER = ("gemini", "deepseek", "grok", "gpt")
_PROVIDER_SECONDS = {"gemini": 20.0, "deepseek": 20.0, "grok": 20.0, "gpt": 35.0}
_ANGLES = {
    ("zzz-roscaelifer", "tea"): ("给六人茶会挑一款红茶和两份点心", "在窗边听风聊今天的一件小事", "为忙完公务的伙伴留一杯温茶"),
    ("zzz-roscaelifer", "invention"): ("设计一个不会打扰别人午睡的小发明", "商量给日常计时器加一个有趣功能", "为茶会设计方便收拾的小装置"),
    ("zzz-roscaelifer", "skywalk"): ("挑一条可以看见云海的散步路线", "安排一段不用赶时间的休息日", "讨论夕阳下适合合照的地方"),
    ("zzz-outer-ring", "special"): ("用今天的心情为不含酒精的特调取一个名字", "给不爱甜的伙伴设计一杯冰饮", "为露天聚会商量每个人喜欢的口味"),
    ("zzz-outer-ring", "roadtrip"): ("找一条能看到落日且方便休息的公路", "商量大钢牙车上应该带什么零食", "在出发前给这次短途旅行选一首歌"),
    ("zzz-outer-ring", "campfire"): ("为晚到的伙伴留一份热夜宵", "围坐时分享今天最想吐槽的一件小事", "预算有限时商量一顿大家都爱吃的饭"),
    ("zzz-mockingbird", "parasol"): ("雨天散步时聊今天的一件小事", "为一起出门挑一条安静的街道", "带着热饮在窗边听雨"),
    ("zzz-mockingbird", "calling-card"): ("为朋友设计一封不透露礼物内容的邀请函", "把一场寻物小游戏布置得像怪盗预告", "为普通聚会想一个优雅的登场方式"),
    ("zzz-mockingbird", "roses"): ("挑一束适合摆在录像店窗边的花", "为下午茶商量甜点与花束搭配", "从电影海报里选一部适合今晚看的片子"),
    ("zzz-obol", "offduty"): ("给刚结束任务的伙伴带些饮料", "在休息室分享今天遇到的一件小事", "商量怎样布置更舒服的休息角"),
    ("zzz-obol", "workshop"): ("用一朵花为小机械发明找灵感", "请席德帮忙改造一个日常小物件", "一起商量工作台上要添什么"),
    ("zzz-obol", "supper"): ("商量拉面和汉堡怎么兼顾", "给怕辣的伙伴准备另一种晚饭", "先挑晚餐还是先挑甜点"),
    ("zzz-yunkui", "tea"): ("雨后山门喝茶时聊一个最近的小困扰", "带一份新点心拜访随便观", "傍晚听风时分享今天一件好事"),
    ("zzz-yunkui", "practice"): ("请同门推荐能每天坚持的小练习", "讨论学新本领时如何面对失败", "用一个生活难题聊每个人的选择"),
    ("zzz-yunkui", "supper"): ("一起安排荤素均衡的晚饭", "讨论澄辉坪逛街买菜路线", "预算有限时挑一道大家都喜欢的菜"),
    ("zzz-krampus", "meet"): ("给刚结束工作的人带一杯热饮", "分享新艾利都街头一件轻松趣事", "商量休息区应该放些什么小物件"),
    ("zzz-krampus", "case"): ("讨论一次遗失物品的小委托", "商量如何公平分配互相帮助的时间", "遇到互相矛盾的说法时怎样先弄清情况"),
    ("zzz-krampus", "dayoff"): ("安排一段能随时歇脚的轻松散步", "商量适合大家口味的便餐", "下雨时安排不赶时间的室内休息日"),
    ("standard", "ideas"): (
        "有限预算下改进一个日常小麻烦", "设计一个五分钟就能开始的小习惯",
        "让家中闲置物品发挥新的用途", "让小空间里的工作与休息更舒服",
        "组织一次大家都愿意参与的小活动", "把突然想到的点子变成一周内可试的原型",
        "减少一种常见的日常浪费", "给一个普通流程增加一点乐趣",
    ),
    ("standard", "learn"): (
        "从厨房里的现象理解一个科学概念", "用排队或交通解释一个抽象概念",
        "用游戏规则讲清概率或信息", "从日常错觉理解感知和记忆",
        "用整理书架解释计算机怎样处理信息", "用天气预报解释不确定性",
        "从一首歌理解声音和节奏", "通过一个可动手的小实验理解能量或运动",
    ),
    ("standard", "compare"): (
        "在家制作与购买现成品的取舍", "小而轻便与功能丰富的工具怎样选",
        "独自完成与找伙伴合作的利弊", "固定计划与弹性安排怎样平衡",
        "一次集中处理与每天少量处理的取舍", "本地保存与云端整理资料的差别",
        "纸面记录与数字记录如何适配场景", "先学基础与先做一个小项目怎样选",
    ),
    ("zzz-trio", "meet"): (
        "第一次进休息室时聊一件轻松的小发现", "休息室里的饮品与小点心",
        "排练间隙怎样让脑袋放松一下", "介绍一件想分享的普通小物件",
        "窗外天气引发的随口聊天", "邀请大家分享今天注意到的一种声音",
        "轻松讨论休息室的一角怎样布置", "拿一个无压力的小问题破冰",
    ),
    ("zzz-trio", "song"): (
        "把一种日常声音当成新歌的起点", "为雨天散步想一小段旋律",
        "用一种颜色连接歌词氛围与舞台灯光", "为清晨到夜晚的变化设计歌曲段落",
        "讨论一段安静开场与热闹副歌的反差", "用一件小物品构想歌词主题",
        "给朋友重逢的心情想一个节奏", "讨论让观众容易参与的一处舞台小设计",
    ),
    ("zzz-trio", "dayoff"): (
        "半天空闲里兼顾散步与找地方歇脚", "遇到下雨时准备一个轻松的备用安排",
        "不赶行程的街区闲逛", "用不多的预算找一点新鲜体验",
        "在安静活动和热闹活动之间做选择", "留出独处时间也保留一起活动的时间",
        "围绕一顿简单的饭安排休息日", "临时决定去哪里但约好轻松的集合方式",
    ),
    ("wangsheng-trio", "meet"): (
        "荧带着一件在璃月街头见到的小事来到往生堂", "聊聊堂前一株花和今天的天气",
        "带一些茶点与在堂里的伙伴歇一会儿", "请大家推荐一处适合看日落的地方",
        "分享路边听来的一个谜语但不预设答案", "商量如何布置堂内的会客小角落",
    ),
    ("wangsheng-trio", "song"): (
        "由一件保存多年的小物品谈起记念的意义", "讨论送别后如何照顾仍在生活的人",
        "从街边花开花落聊眼前值得珍惜的小事", "聊聊旧日习俗如何适应今天的生活",
        "谈谈一顿家常饭为什么会让人想起故人", "讨论安静陪伴与开口安慰各适合什么时刻",
    ),
    ("wangsheng-trio", "dayoff"): (
        "围绕万民堂的一顿晚饭商量各自想吃的口味", "吃完饭是在港边散步还是坐着喝茶",
        "下雨时安排一场不赶时间的室内聚餐", "用家常食材准备一道适合分享的菜",
        "在看戏和逛夜市之间商量一个轻松选择", "提议给忙完堂务的伙伴留一份热饭",
    ),
}


def _fingerprint(text: str) -> str:
    """Whitespace or punctuation changes must not disguise the same opener."""
    return "".join(char.casefold() for char in unicodedata.normalize("NFKC", text)
                   if not char.isspace() and unicodedata.category(char)[0] not in "PZC")


class StarterGenerator:
    """Keep one instance per app: no queued jobs, at most two model processes."""

    def __init__(self, gateway, *, timeout=75.0, attempt_timeout=None,
                 max_attempts=3, max_concurrent=2, history_limit=6):
        self.gateway = gateway
        self.timeout = max(0.01, min(float(timeout), 75.0))
        self.attempt_timeout = None if attempt_timeout is None else max(0.01, float(attempt_timeout))
        self.max_attempts = max(1, min(int(max_attempts), 3))
        self.history_limit = max(1, min(int(history_limit), 12))
        self._slots = threading.BoundedSemaphore(max(1, min(int(max_concurrent), 2)))
        self._lock = threading.Lock()
        self._recent: dict[tuple[str, str], deque[str]] = {}
        self._last_angle: dict[tuple[str, str], str] = {}
        self._random = random.SystemRandom()
        self._closed = threading.Event()
        self._active: set[threading.Event] = set()

    def cancel_all(self):
        """Cancel in-flight generation and reject new work during shutdown."""
        with self._lock:
            self._closed.set()
            for cancel in self._active:
                cancel.set()

    def _context(self, key):
        with self._lock:
            recent = list(self._recent.get(key, ()))
            choices = [angle for angle in _ANGLES[key] if angle != self._last_angle.get(key)]
            angle = self._random.choice(choices)
            self._last_angle[key] = angle
        return recent, angle

    @staticmethod
    def _prompt(room, starter, angle, recent):
        if room["id"] == "zzz-roscaelifer":
            scene = ("只为用户起草发给诺姆、维琳娜、希格莉德、克拉蕾、洛克茜、林德薇恩的日常开场。"
                     "组合为罗斯凯利法，群聊名天空之城，不凭群名假定用户就是法厄同，不预设恋人或追星关系。"
                     "茶会、休息日与小发明为同人日常，不替角色回答，不编造官方事件、身世秘密和共同往事。")
        elif room["id"] == "zzz-mockingbird":
            scene = ("只为用户起草发给薇薇安、雨果的日常开场，聊天室名法厄同一生推，组合反舌鸟。"
                     "默认任务间隙，不凭群名假定用户就是法厄同，不预设恋人关系，不替角色写回答与决定。"
                     "预告函主题是礼物、邀请或日常小游戏，不编造官方案件、身世秘密或共同往事。")
        elif room["id"] == "zzz-obol":
            scene = ("只为用户起草发给席德、鬼火、奥菲丝、扳机、11号、白银安比的日常开场。场景为404小队休息整备区。"
                     "鬼火是机械龙头枪械，与奥菲丝为独立人格；白银安比为用户指定的跨阵营成员。"
                     "不替角色写回应，不预设上下级、恋爱或共同往事。")
        elif room["id"] == "zzz-outer-ring":
            scene = ("只为用户起草发给柏妮思、凯撒、露西、莱特、波可娜、派派的开场消息。场景为外环旅途休息、特调和聚餐。"
                     "相亲相爱一家人是群聊名，不预设血缘、恋爱或共同往事。饮品和设备燃油分清，不替角色作出回应。")
        elif room["id"] == "zzz-yunkui":
            scene = ("只为用户起草发给仪玄、叶瞬光、潘引壶、橘福福的开场消息。场景是随便观的休息时光与澄辉坪日常。"
                     "用户是到访朋友，不预设拜师或恋爱关系；不替角色写回应、心理和决定，不编造官方剧情与共同往事。")
        elif room["id"] == "zzz-krampus":
            scene = ("只为用户起草发给琉音、照、菲欧妮、般岳、普罗米娅的开场消息。场景是黑枝任务间隙或新艾利都轻松日常。"
                     "用户默认是来访朋友，不预设上司或恋爱关系；不替角色写回应、心理或决定，不编造官方案件和共同往事。")
        elif room["id"] == "wangsheng-trio":
            scene = ("你只为用户起草将发给钟离、胡桃、若娜瓦、香菱、魈、兹白、派蒙的开场消息。"
                     "用户在故事中是旅行者荧，场景是若娜瓦在往生堂工作半年后的璃月日常。"
                     "只起草用户可以说的话，不替任何角色写回应、动作、内心或决定。"
                     "不预设恋爱、和解或共同私密经历，不编造官方剧情，不强迫所有角色都回应。")
        elif room["id"] == "zzz-trio":
            scene = ("你只为用户起草将发给千夏、南宫羽、爱芮的开场消息。场景是排练后休息室、音乐或轻松日常。"
                     "用户是来聊天的朋友；不要预设经纪人、恋人或家属关系，不编造共同经历或官方剧情。"
                     "不要替任何角色写回应、动作、内心或决定，也不要自称这三位角色。")
        else:
            scene = ("你只为用户起草将发给 DeepSeek、Gemini、GPT、Grok 的讨论开场。"
                     "挑一个具体、贴近日常、适合从不同角度讨论的问题，不扮演其他聊天室的角色。")
        task = {"room": room["name"], "theme": starter["title"], "keywords": starter["description"],
                "angle": angle, "avoidRepeating": recent}
        return f"""现在执行开场消息起草任务，不是回复聊天，也不是延续你自己的角色对白。
{scene}
依据以下主题关键词与本次随机切入点，写一条新的、用户视角的中文开场消息，约80到180字。
至少加入一个具体情境和一个可讨论的选择或问题，让用户可以直接发送。
内容自然连贯，不要列多个方案、加标题、解释生成过程或给出答案。不添加问候以外的模型自我介绍。
每次改变实质情境或讨论角度，不只是改同义词或标点。avoidRepeating仅是此前生成的候选开场，不是真实对话历史；不要复述它们。
<starter_task>
{json.dumps(task, ensure_ascii=False)}
</starter_task>
没有提供任何真实聊天历史，不能声称知道用户的过去经历或偏好。
<conversation_data>
[]
</conversation_data>
请仅返回一个 JSON 对象，不能添加代码围栏或额外说明：
{{"speak": true, "to": "everyone", "content": "一条可以直接由用户发送的新开场消息"}}
"""

    @staticmethod
    def _content(raw):
        if not isinstance(raw, str):
            raise ValueError("invalid result")
        decision = parse_decision(raw)
        content = decision["content"]
        # Allow modest punctuation/token-count variance around the 80–180 target.
        if not decision["speak"] or not 60 <= len(content) <= 220:
            raise ValueError("invalid opener length")
        if sum("\u4e00" <= char <= "\u9fff" for char in content) < 30:
            raise ValueError("not a Chinese opener")
        if re.search(r"(?:^|[\r\n])\s*(?:千夏|南宫羽|爱芮|钟离|胡桃|若娜瓦|香菱|魈|兹白|派蒙|DeepSeek|Gemini|GPT|Grok)\s*[:：]", content, re.I):
            raise ValueError("character dialogue instead of a user opener")
        return content

    def generate(self, room_id, starter_id):
        room = get_room(room_id)  # Validation precedes even acquiring a slot.
        if not isinstance(starter_id, str):
            raise ValueError("未知的开场主题，请重新选择开场卡。")
        starter = next((item for item in room["starters"] if item["id"] == starter_id), None)
        if starter is None:
            raise ValueError("未知的开场主题，请重新选择开场卡。")
        if self._closed.is_set():
            raise GatewayError("开场生成服务已停止。")
        if not self._slots.acquire(blocking=False):
            raise GatewayError("开场方案正在生成中，请稍后再试。")
        try:
            try:
                configured = {item["id"] for item in self.gateway.status() if item.get("configured")}
            except Exception:
                raise GatewayError("暂时无法读取模型连接，请刷新连接后重试。") from None
            providers = [provider for provider in _PROVIDER_ORDER if provider in configured]
            if not providers:
                raise GatewayError("尚未连接可用模型，请先连接 Gemini、DeepSeek、GPT 或 Grok。")
            key = (room_id, starter_id)
            deadline = time.monotonic() + self.timeout
            repeated, timed_out = False, False
            for attempt in range(self.max_attempts):
                if self._closed.is_set():
                    raise GatewayError("开场生成已停止。")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                provider = providers[min(attempt, len(providers) - 1)]
                recent, angle = self._context(key)
                prompt = self._prompt(room, starter, angle, recent)
                cancel = threading.Event()
                with self._lock:
                    if self._closed.is_set():
                        raise GatewayError("开场生成已停止。")
                    self._active.add(cancel)
                budget = min(remaining, self.attempt_timeout or _PROVIDER_SECONDS[provider])
                timer = threading.Timer(budget, cancel.set)
                timer.daemon = True
                timer.start()
                try:
                    raw = self.gateway.respond(provider, prompt, cancel)
                    if cancel.is_set() or time.monotonic() >= deadline:
                        timed_out = True
                        continue
                    content = self._content(raw)
                    with self._lock:
                        if self._closed.is_set():
                            raise GatewayError("开场生成已停止。")
                        history = self._recent.setdefault(key, deque(maxlen=self.history_limit))
                        if any(_fingerprint(content) == _fingerprint(previous) for previous in history):
                            repeated = True
                            continue
                        history.append(content)
                    return {"roomId": room_id, "starterId": starter_id, "provider": provider, "prompt": content}
                except Exception:
                    # Never pass upstream diagnostics, local paths, keys, or model
                    # payloads to the browser. All fallback attempts are bounded.
                    timed_out = timed_out or cancel.is_set()
                finally:
                    timer.cancel()
                    cancel.set()
                    with self._lock:
                        self._active.discard(cancel)
            if self._closed.is_set():
                raise GatewayError("开场生成已停止。")
            if repeated:
                raise GatewayError("暂时没能生成不同的开场方案，请换个主题或稍后再试。")
            if timed_out:
                raise GatewayError("开场方案生成超时，请稍后再试。")
            raise GatewayError("开场方案生成失败，请稍后重试或刷新模型连接。")
        finally:
            self._slots.release()
