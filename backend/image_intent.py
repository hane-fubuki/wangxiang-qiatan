"""Conservative, local image requests and immediately preceding invitations.

History uses the app's message dictionaries. Only the latest user turn's
assistant replies can supply an invitation; no model or external service runs.
"""
from __future__ import annotations

import re
import unicodedata


_NAMES = r"(?:千夏|南宫羽|南宫|爱芮|GPT|Gemini|DeepSeek)"
_GROUP_PHOTO = r"合(?:个|张|一张)?影"
_DRAW_REQUEST = r"(?:画(?!面|质|风|师|法|技|功)|绘制|重画|重绘)\s*\S+"
_VISUAL_PRODUCTS = (
    "图片", "图像", "照片", "相片", "插画", "插图", "头像", "立绘", "壁纸", "海报",
    "漫画", "封面", "图画", "素描", "油画", "水彩", "示意图", "流程图", "路线图",
    "概念图", "设计图", "表情包", "宣传图", "像素画", "合影", "合照", "自拍",
)
_NONVISUAL_OBJECTS = (
    "名字", "名称", "昵称", "记录", "聊天", "语气", "说话", "设定", "设置", "skill",
    "代码", "文案", "句子", "这句话", "文章", "文本", "回复", "答案", "表格", "清单",
)
_VISUAL_OBJECTS = (
    "背景", "头发", "发色", "衣服", "服装", "裙子", "眼睛", "瞳色", "肤色", "姿势",
    "表情", "构图", "画面", "人物", "角色", "边框", "水印", "色调", "光线", "阴影",
    "圆圈", "方块", "线条", "轮廓", "透明", "像素", "分辨率", "尺寸", "清晰度",
)
_PHOTO_PATTERNS = (
    rf"(?:{_GROUP_PHOTO}|合照|自拍|拍照)",
    rf"拍(?:摄)?(?:一张|几张|两张|张|一组|个)?(?:照片|相片|合照|自拍|{_GROUP_PHOTO}|照)",
    rf"(?:拍(?:摄)?|来|照)(?:一张|几张|两张|张|一组)?[^,，。!?？！;；\n]{{1,40}}的(?:照片|相片|合照|自拍|{_GROUP_PHOTO})",
    rf"(?:来|照)(?:一张|几张|张|一组)?(?:自拍|合照|照片|相片|{_GROUP_PHOTO})",
)
_EDIT_VERBS = r"(?:改成|改为|换成|变成|修改|编辑|调整|去掉|移除|去除|添加|增加|隐藏|删除|换掉|抠图|裁剪|裁切|放大|缩小|上色|重画|重绘)"
_CANCEL_PATTERNS = (
    r"(?:先别|暂时别|先不|暂时不|不要再|不用再|不需要再).{0,8}(?:画|拍|生成|生图|修改|编辑)",
    rf"(?:不用|不必|无需|不要|不需要).{{0,6}}(?:生图|生成图片|生成图像|画图|拍照|{_GROUP_PHOTO}|合照)",
    rf"(?:取消|停止|撤销).{{0,8}}(?:生图|生成|绘图|画图|拍照|{_GROUP_PHOTO}|请求)",
    r"(?:别|不要)(?:画|拍|生成|修改)(?:了|啦|呀|啊|吧|[。!！]|$)",
    r"(?:只是|仅仅是|只是在)(?:举个例子|举例|讨论|评价|描述|说说)",
    r"(?:只|仅)(?:需|要|想)?(?:说说|解释|讨论|聊聊|讲讲).{0,8}(?:思路|方法|步骤|原理)",
)
_META_PATTERNS = (
    r"什么意思|是什么意思|怎么理解|指的是什么|翻译成|翻译为|译成|英文怎么说|英语怎么说",
    r"(?:这句话|这句|句子|这段话).{0,15}(?:含义|翻译|解释|语法|分析|英文|英语)",
    r"(?:如何|怎样|怎么)(?:才能|才|去|把|帮|给)?.{0,12}(?:画|拍|生成|绘制|改图)",
    r"(?:教我|教一下|教教我).{0,12}(?:画|拍|生成|绘制|改图)",
    r"(?:需要|要|得)(?:多长时间|多久|多少(?:时间|钱|费用|步骤))",
    r"(?:生成|画|绘制|拍照).{0,30}(?:教程|步骤|流程|原理|方法)(?:是什么|有哪些|怎么|[?？]|$)",
)
_DEFERRED = r"(?:如果|假如|要是|下次|改天|明天|以后|有空再|有空时|等会|等到|等你|等下|计划|打算)"
_PAST = r"昨天|前天|去年|之前|以前|曾经|上次|刚才|已经|拍过|拍了|画过|画了|生成过|生成了"


def _plain(content):
    if not isinstance(content, str):
        return ""
    text = unicodedata.normalize("NFKC", content).strip()
    # Examples and quotations are data, including code in otherwise normal prose.
    text = re.sub(r"```[\s\S]*?(?:```|$)|~~~[\s\S]*?(?:~~~|$)", " ", text)
    text = re.sub(r"(?m)^\s*>.*$", " ", text)
    text = re.sub(r"`[^`\n]*`|“[^”]*”|‘[^’]*’|「[^」]*」|『[^』]*』|\"[^\"\n]*\"|'[^'\n]*'", " ", text)
    text = re.sub(r"^(?:@" + _NAMES + r"\s*[,，:：]?\s*)+", "", text, flags=re.I)
    # Keep explicit present-tense roleplay actions; later rules still exclude
    # a past action such as "(举起手机拍了张照片)".
    text = re.sub(r"^\(([^()\n]{0,80})\)\s*", r"\1，", text)
    text = re.sub(r"^\[([^\[\]\n]{0,80})\]\s*", r"\1，", text).strip()
    return text


def _blocked(text):
    if not text:
        return True
    if any(re.search(pattern, text, re.I) for pattern in (*_CANCEL_PATTERNS, *_META_PATTERNS)):
        return True
    if re.match(r"(?:别|不要|不用|不必|无需|不需要|取消|算了|先等等|先等一下)", text):
        return True
    return False


def _clauses(text):
    return [part.strip() for part in re.split(r"[,，。!！;；\n]+", text) if part.strip()]


def _request_core(text):
    """Remove an address and polite/group lead-in, keeping the action intact."""
    text = re.sub(r"^(?:" + _NAMES + r"(?:和我|和我们|和大家)?[,，:：]?\s*)", "", text, flags=re.I)
    for _ in range(4):
        before = text
        text = re.sub(r"^(?:请|麻烦|现在|今天|再|重新|一起|大家|我们|咱们|三位|三人|我和你|你和我|你们|你)\s*", "", text)
        text = re.sub(r"^(?:能不能|能否|可不可以|可以|能)?(?:帮我们|给我们|为我们|帮我|给我|为我|替我)\s*", "", text)
        if text == before:
            break
    # Keep the actual subject in quoted prompts out of intent parsing; the
    # original message is retained later for the generation request itself.
    return re.sub(r"^根据.{0,80}?(?=生成|绘制|画|制作|拍|修改|编辑)", "", text).strip()


def _deferred_or_past(clause):
    if re.search(_DEFERRED, clause):
        return True
    # Deictic references in edits ("刚才的图片") are handled by the edit rule.
    return bool(re.search(_PAST, clause))


def _photo(core):
    # An explicit request can name its subjects by pronoun. Keep this local to
    # photography so "给她画画的教程" does not become a drawing command merely
    # because its recipient was stripped. The original subject remains in the
    # generation context for the engine to resolve against recent messages.
    core = re.sub(r"^(?:能不能|能否|可不可以|可以|能)?(?:给|帮|为|替)(?:她们|他们|它们|她|他|它)(?:来)?", "", core)
    # People can precede the action ("我和千夏一起合影"), or follow it
    # ("拍你们三人的合照"). Strip this after the recipient so "给她和我
    # 拍张合照" also keeps the photo action, without changing its subjects.
    social = re.match(rf"^(?:我们|咱们|我)?(?:想)?和[^,，。!?？！;；\n]{{1,40}}?(?=拍|{_GROUP_PHOTO}|合照|自拍)", core)
    if social:
        core = core[social.end():]
    return any(re.match(pattern, core) for pattern in _PHOTO_PATTERNS)


def _contextual_creation(core):
    """Recognize an immediate command whose appearance comes from prior chat.

    "刚才" describes the reference here, not when the action happened. Require
    a complete imperative so past recollections and discussions stay excluded.
    """
    reference = r"(?:按(?:照)?|照)(?:刚才|之前|前面|上面)(?:(?:说|描述|提到)的|的)?(?:样子|形象|造型|场景|服装|姿势|设定)?"
    action = r"(?:来)?(?:画|绘制|生成|拍)(?:(?:一|几|两)?(?:张|幅)(?:图片|照片|插画|图|照)?)?"
    ending = r"(?:吧|呀|啊|好吗|好不好|可以吗|行吗)?[?？~～]*"
    return bool(re.fullmatch(reference + action + ending, core))


def _edit(core, has_images):
    explicit_image = any(word in core for word in _VISUAL_PRODUCTS) or bool(re.search(r"此图|这幅图|这张图|上一张图|上传的图", core))
    if not explicit_image and any(word.lower() in core.lower() for word in _NONVISUAL_OBJECTS):
        return False
    visual_object = any(word in core for word in _VISUAL_OBJECTS) or bool(re.search(r"[红橙黄绿青蓝紫黑白灰粉金银]色?(?:圈|圆|块|球|线)", core))
    if not (explicit_image or (has_images and visual_object)):
        return False
    if re.match(_EDIT_VERBS, core):
        return True
    if re.match(r"(?:把|将|让)", core) and re.search(_EDIT_VERBS, core):
        return True
    return has_images and visual_object and bool(re.search(_EDIT_VERBS, core))


def _direct(text, has_images):
    if re.match(r"/(?:生图|画图)(?:\s|$)", text):
        return True
    # A leading condition governs later clauses too ("如果有空，画只猫").
    if re.match(_DEFERRED, _request_core(text)):
        return False
    for clause in _clauses(text):
        core = _request_core(clause)
        if not core or re.match(r"(?:不要|不用|别|无需|不需要)", core):
            continue
        if re.search(r"(?:很|真|挺|太|非常)(?:好看|漂亮|可爱|有趣|开心|不错|好玩|精致|棒)[呀啊呢了吗?？~～]*$", core):
            continue
        if re.search(r"(?:是我的爱好|是我的兴趣|好玩吗|有趣吗)[?？]*$", core):
            continue
        if re.match(r"画(?:出(?:来)?的|的|得)", core) or re.search(r"(?:效果|成品)(?:很|真|挺|非常)?(?:不错|很好|漂亮|好看)[呀啊呢]*$", core):
            continue
        if re.search(_DEFERRED, clause):
            continue
        if _edit(core, has_images):
            return True
        if _contextual_creation(core):
            return True
        if _deferred_or_past(clause):
            continue
        if _photo(core):
            return True
        if re.match(_DRAW_REQUEST, core):
            return True
        if re.match(r"(?:生成|制作|设计)\s*", core):
            if any(word in core for word in _VISUAL_PRODUCTS):
                return True
            if re.match(r"(?:生成|制作)一张\S+", core) and not any(word in core for word in _NONVISUAL_OBJECTS):
                return True
    return False


def _confirmation(text):
    parts = _clauses(text)
    if not parts or len(text) > 70:
        return False
    patterns = (
        r"(?:好[呀啊哇的]?|可以[呀啊]?|行[呀啊]?|嗯嗯?|没问题|同意|听你的)(?:那就)?(?:来一张|来一幅|来吧|拍吧|画吧|开始吧)?",
        r"(?:那就|就)?(?:来一张|来一幅|来吧|拍吧|画吧|开始吧)",
        r"(?:那)?就按(?:你|你们|大家)(?:刚才)?说的(?:拍|画|来)",
        r"(?:那就|就)?(?:这样|这么)(?:拍|画)",
    )
    return all(any(re.fullmatch(pattern + r"[?？~～]*", part.strip()) for pattern in patterns) for part in parts)


def _invitation(text):
    if _blocked(text):
        return False
    for clause in _clauses(text):
        if _deferred_or_past(clause):
            continue
        offer = bool(re.search(r"要不要|不如|一起|我来|我可以|给你|帮你|为你|想不想|好不好|好吗|怎么样|吧[?？~～]*$", clause))
        action = bool(re.search(rf"拍照|{_GROUP_PHOTO}|合照|自拍|拍(?:一)?张(?:照|照片)?|画(?:一|只|张|幅)|绘制|生成.{{0,24}}(?:图片|图像|海报|头像|封面)", clause))
        if offer and action:
            return True
    return False


def _recent_invitation(content, history):
    if not isinstance(history, (list, tuple)):
        return None
    messages = [message for message in history if isinstance(message, dict) and message.get("role") in {"user", "assistant"}]
    # _generate may already have appended the current user message, whereas
    # start normally checks intent before appending it.
    tail_content = messages[-1].get("content") if messages else None
    if messages and messages[-1].get("role") == "user" and isinstance(tail_content, str) and tail_content.strip() == content.strip():
        messages = messages[:-1]
    last_user = next((index for index in range(len(messages) - 1, -1, -1) if messages[index]["role"] == "user"), -1)
    replies = messages[last_user + 1:]
    if not replies or len(replies) > 12:
        return None
    if any(message.get("kind") == "image" or message.get("attachments") for message in replies):
        return None
    for message in reversed(replies):
        original = message.get("content", "")
        text = _plain(original)
        if not text:
            continue
        if _blocked(text):
            return None
        if _invitation(text):
            speaker = message.get("speakerName") or message.get("provider") or "助手"
            speaker = str(speaker).replace("\n", " ").strip()[:60]
            return speaker, original.strip()[:1800]
        # A later suggestion about something else supersedes the image offer.
        # Short acknowledgements may instead come from another group member.
        if re.search(r"要不要|不如|怎么样|好不好|好吗|吧[。!！?？]*$", text):
            return None
        if len(text) > 100 and not re.search(rf"手机|镜头|拍照|{_GROUP_PHOTO}|合照|自拍|绘图|画画", text):
            return None
    return None


def image_requested(content, intent="auto", has_images=False, history=None) -> bool:
    """Recognize an immediate request; explicit image mode remains authoritative."""
    if intent == "image":
        return True
    if intent != "auto":
        return False
    text = _plain(content)
    if _blocked(text):
        return False
    if (re.search(r"放大.{0,12}(?:看|读|识别|辨认)", text)
            and not re.search(r"生成|绘制|重画|重绘|保存|导出|发给|发送|发我|/生图|/画图", text)):
        return False
    if _direct(text, has_images):
        return True
    return _confirmation(text) and _recent_invitation(content, history) is not None


def image_edit_requested(content, has_images=False) -> bool:
    """True only when the first actionable image request edits an image.

    A new photo with a later background instruction must not inherit an old
    image. Greetings and ordinary commentary can precede a genuine edit.
    """
    text = _plain(content)
    if _blocked(text) or re.match(_DEFERRED, _request_core(text)):
        return False
    for clause in _clauses(text):
        if not _direct(clause, has_images):
            continue
        core = _request_core(clause)
        if re.match(_EDIT_VERBS, core) and _edit(core, has_images):
            return True
        if (_photo(core) or re.match(_DRAW_REQUEST, core)
                or re.match(r"(?:生成|制作|设计)|/(?:生图|画图)(?:\s|$)", core)):
            return False
        return _edit(core, has_images)
    return False


def image_request_context(content, history=None) -> str:
    """Return the current request, adding only an accepted recent invitation."""
    if not isinstance(content, str):
        return ""
    current = content.strip()
    text = _plain(current)
    if not _blocked(text) and _confirmation(text):
        invitation = _recent_invitation(current, history)
        if invitation:
            speaker, proposal = invitation
            return f"{speaker}的提议：{proposal}\n用户当前要求：{current}"
    return current
