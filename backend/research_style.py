"""Conservative presentation cleanup for already researched chat replies.

This module does not verify facts or change stored research. Callers decide whether
the user wants sources and whether a research report exists before using cleanup.
Only known source URLs are removed; code, images, and unrelated links survive.
"""
from __future__ import annotations

import html
import re
from urllib.parse import unquote, urlsplit


_SOURCE_NOUN = r"(?:出处|来源|原文|参考文献|参考资料|引用|(?:官方|官网|下载)?(?:地址|网址|链接)|URL|sources?|references?|citations?|links?)"
_NEGATIVE_REQUEST = re.compile(
    r"(?:不要|不用|无需|不必|别|不需要|禁止|不想看|不想要|不显示|不展示|不列)"
    r"[^，,。；;！？!?\n]{0,22}" + _SOURCE_NOUN
    + r"|\b(?:do not|don't|no need to|without|omit|hide)\s+(?:\w+\s+){0,5}" + _SOURCE_NOUN,
    re.I,
)
_POSITIVE_REQUEST = re.compile(
    r"(?:给|发|提供|附上|附带|列出|展示|显示|标明|注明|告诉|贴|找|查|要看|想看|想要|只要|就要|只需|仅需)"
    r"[^，,。；;！？!?\n]{0,18}" + _SOURCE_NOUN
    + r"|(?:出处|来源|原文|参考文献|参考资料|链接|网址|URL)\s*(?:到底|究竟|具体)?\s*(?:在哪|哪里|是什么|是哪|呢|吗|怎么说|怎么写|给我|发我|[？?])"
    + r"|(?:从哪|哪里|哪儿|什么地方)[^，,。；;！？!?\n]{0,8}(?:看到|看见|查到|读到|找到|听说|得知)"
    + r"|(?:官方|官网|下载)(?:地址|网址|链接)"
    + r"|(?:怎么|如何|在哪(?:里)?|哪里可以)下载|官网(?:在哪|在哪里|怎么进|怎么打开)"
    + r"|\b(?:show|give|provide|include|cite|list|send|share)\b[^.!?\n]{0,35}\b(?:sources?|references?|citations?|links?|URL)\b"
    + r"|\bwhere\s+(?:did\s+you\s+(?:read|see|find)|is\s+the\s+source)\b",
    re.I,
)


def sources_requested(text: str) -> bool:
    """Recognize explicit source requests, with scoped negative instructions.

    A later clear request can override an earlier omission ("不要长清单，给我原文").
    Merely asking to verify a fact or mentioning an official announcement does not.
    """
    text = text or ""
    negatives = list(_NEGATIVE_REQUEST.finditer(text))
    positives = [match for match in _POSITIVE_REQUEST.finditer(text)
                 if not any(neg.start() <= match.start() < neg.end() for neg in negatives)]
    if re.fullmatch(r"\s*" + _SOURCE_NOUN + r"\s*[？?。.!！]*\s*", text, re.I):
        return True
    if not positives:
        return False
    # A request for one original/link can coexist with rejecting a bibliography.
    prohibitions = []
    for match in negatives:
        clause = re.split(r"[，,。；;！？!?\n]", text[match.start():], maxsplit=1)[0]
        if not re.search(r"清单|列表|长串|一长串|一堆|大量", clause):
            prohibitions.append(match)
    return not prohibitions or positives[-1].start() > prohibitions[-1].start()


_MARKDOWN_LINK = re.compile(
    r"(?<!!)\[([^\]\n]+)\][ \t]*(?:\n[ \t]*)?\(\s*"
    r"(https?://(?:\\.|[^\s()]|\((?:\\.|[^()]|\([^()]*\))*\))+)"
    r"(?:\s+[\"'][^\n]*?[\"'])?\s*\)", re.I,
)
_BARE_URL = re.compile(r"https?://[^\s<>\[\]\"'‘’“”，。；！？（）]+", re.I)
_SOURCE_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:资料来源|信息来源|参考来源|参考资料|参考文献|相关来源|来源|出处|Sources?|References?|Citations?)"
    r"(?:\*\*)?\s*[:：]?\s*(?:\*\*)?\s*$", re.I,
)
_INLINE_SOURCE_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:资料来源|信息来源|参考来源|参考资料|参考文献|相关来源|来源|出处|Sources?|References?|Citations?)"
    r"(?:\*\*)?\s*[:：]\s*(?:\*\*)?\s*", re.I,
)
_CITATION_LABEL = re.compile(
    r"^(?:\d+(?:[,，、\s]+\d+)*|来源\s*\d*|source\s*\d*|参考\s*\d*)$"
    r"|^(?:官网(?:公告|说明|信息|网站)?|官方(?:公告|说明|文档|消息|新闻|资料|网站|页面)"
    r"|[\w\u4e00-\u9fff]{0,10}(?:公告|新闻|百科|维基|原文|来源|报道|参考资料)"
    r"|official(?: announcement| source| news)?|wikipedia|news|source)$", re.I,
)
_SEMANTIC_LABEL = re.compile(r"不|未|尚|没|可能|或许|暂|待定|无法|确认|公布了|发布了|定于|举行|需要|可以|\b(?:not|may|might|could|unconfirmed)\b", re.I)
_FUNCTIONAL_LABEL = re.compile(r"下载|打开|访问|安装|购买|注册|登录|报名|预约|在线使用|\b(?:download|open|install|sign in|sign up|register|buy)\b", re.I)
_SEARCH_PREFIX = re.compile(
    r"(?m)^([ \t]*(?:>[ \t]*)?)(?:"
    r"(?:我)?(?:刚刚|刚|刚才)?(?:去|又)?(?:核实|核查|查证|查|搜|检索|搜索)(?:过|了)?(?:一下|一遍|下)"
    r"|(?:我)?刚(?:刚)?(?:去)?(?:查过|搜过|核实过|查了|搜了)"
    r"|根据(?:刚才的|刚刚的|这次的|本次的)?(?:检索|搜索|联网查询|查询|查证|核实)结果"
    r"|(?:我)?(?:刚才|刚刚)?(?:在网上|上网|联网)(?:查|搜|核实|检索)(?:了|过)?(?:一下|下)?"
    r")[ \t]*[，,：:][ \t]*"
)


def _url_key(value: str):
    try:
        value = html.unescape(value).replace(r"\(", "(").replace(r"\)", ")").strip()
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return None
        # Fragments and a trailing slash do not identify a different source page.
        return (parsed.netloc.lower(), unquote(parsed.path).rstrip("/"), parsed.query)
    except (TypeError, ValueError):
        return None


def _protect(content: str):
    prefix = "\ue000RESEARCH_STYLE_"
    while prefix in content:
        prefix += "_"
    protected = []

    def save(match):
        token = f"{prefix}{len(protected)}\ue001"
        protected.append(match.group(0))
        return token

    # Protect fences before inline code, including an unfinished trailing fence.
    fence = re.compile(r"(?m)^ {0,3}(?P<fence>`{3,}|~{3,})[^\n]*\n[\s\S]*?(?:^ {0,3}(?P=fence)[ \t]*(?=\n|$)|\Z)")
    content = fence.sub(save, content)
    inline = re.compile(r"(?<!`)(`+)(?!`)[\s\S]*?(?<!`)\1(?!`)")
    content = inline.sub(save, content)
    image_refs = re.findall(r"!\[([^\]\n]*)\]\[([^\]\n]*)\]", content)
    for label, reference in image_refs:
        reference = reference or label
        content = re.sub(r"(?m)^ {0,3}\[" + re.escape(reference) + r"\]:[^\n]*", save, content)
    image = re.compile(r"!\[[^\]\n]*\](?:\((?:\\.|[^()\n]|\([^()\n]*\))*\)|\[[^\]\n]*\])")
    content = image.sub(save, content)
    # A useful destination must remain clickable even if it was also consulted
    # as a research source (for example Python's official download page).
    content = _MARKDOWN_LINK.sub(lambda m: save(m) if _FUNCTIONAL_LABEL.search(m.group(1)) else m.group(0), content)
    return content, protected, prefix


def _strip_numeric_citations(text: str) -> str:
    """Remove explicit footnote syntax; bare numeric brackets are ambiguous."""
    def replace(match):
        before = text[:match.start()]
        after = text[match.end():]
        line_before = before.rsplit("\n", 1)[-1]
        if not line_before.strip() and after.startswith(":"):
            return match.group(0)
        return ""

    return re.sub(r"\[\^\d+\]", replace, text)


def clean_research_reply(content: str, sources: list[dict]) -> str:
    """Remove research presentation scaffolding without rewriting the answer.

    Unknown URLs remain intact. Known linked page titles become plain text unless
    they are recognizable citation labels or form a standalone citation item.
    Empty output is intentional: the caller should then avoid sending a reply.
    """
    if not content:
        return ""
    keys = {_url_key(source.get("url", "")) for source in (sources or []) if isinstance(source, dict)}
    keys.discard(None)
    titles = {str(source.get("title", "")).strip() for source in (sources or []) if isinstance(source, dict)}
    titles.discard("")
    text, protected, prefix = _protect(content)

    def known(url):
        return _url_key(url) in keys

    def bare(match):
        url = match.group(0)
        candidate = url
        while candidate:
            if known(candidate):
                return url[len(candidate):]
            if candidate[-1] not in ".,;:!?)]}":
                break
            candidate = candidate[:-1]
        return url

    def no_links(value, keep_labels):
        def link(match):
            if not known(match.group(2)):
                return match.group(0)
            label = match.group(1)
            citation = not _SEMANTIC_LABEL.search(label) and (
                _CITATION_LABEL.search(label) or (not keep_labels and label in titles))
            return "" if citation else label
        value = _MARKDOWN_LINK.sub(link, value)
        value = re.sub(r"<\s*(https?://[^<>\s]+)\s*>", lambda m: "" if known(m.group(1)) else m.group(0), value)
        return _BARE_URL.sub(bare, value)

    # Collapse only complete citation parentheses; this also recognizes a linked
    # source title that is not itself an obvious label such as "official news".
    def parenthetical(match):
        value = match.group(1)
        stripped = no_links(value, False)
        if stripped != value and not re.sub(r"[\s,，、;；:：\[\]\d*]+", "", stripped):
            return ""
        return match.group(0)

    text = _MARKDOWN_LINK.sub(lambda m: m.group(0).replace("\n", "") if known(m.group(2)) else m.group(0), text)
    text = re.sub(r"（([^（）]*)）", parenthetical, text)
    text = re.sub(r"(?<![\]!])\(((?:[^()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*)\)", parenthetical, text)
    # ASCII parentheses containing markdown links need balanced URL parentheses;
    # the general empty-parenthesis cleanup below handles them after link removal.
    lines = []
    for original in text.splitlines(keepends=True):
        newline = "\n" if original.endswith("\n") else ""
        line = original.rstrip("\r\n")
        if _SOURCE_HEADING.fullmatch(line):
            lines.append(newline)
            continue
        probe = _INLINE_SOURCE_HEADING.sub("", line)
        without_links = no_links(probe, False)
        only_citation = without_links != probe and not re.sub(r"[\s\-+*\d.、,，;；:：()（）\[\]^]+", "", without_links)
        if only_citation:
            lines.append(newline)
            continue
        before_links = line
        line = no_links(line, True)
        if line != before_links:
            line = re.sub(r"(?:[,，;；]\s*)?(?:来源|出处|参考|参见|详见)\s*[:：]\s*(?=[。.!！?？]|$)", "", line)
        # A numeric reference definition pointing to a known URL has no useful body.
        if line != original.rstrip("\r\n") and re.fullmatch(r"\s*\[\^?\d+\]:?\s*", line):
            lines.append(newline)
            continue
        lines.append(line + newline)
    text = "".join(lines)
    # A markdown link may wrap between its label and URL, so clean once more over
    # the whole text after the line-level citation list handling.
    text = no_links(text, True)
    text = _strip_numeric_citations(text)
    text = re.sub(r"cite[^\n]*|【\d+†[^】\n]*】", "", text)
    while True:
        without_prefix = _SEARCH_PREFIX.sub(r"\1", text)
        if without_prefix == text:
            break
        text = without_prefix
    text = re.sub(r"[（(]\s*(?:(?:来源|参考|参见|详见|出处)\s*[:：]?\s*)?[,，、;；]*\s*[）)]", "", text)
    text = re.sub(r"(?m)^\s*[-+*]\s*$", "", text)
    text = re.sub(r"([，,、;；])(?:[ \t]*[，,、;；])+", r"\1", text)
    text = re.sub(r"[，,、;；][ \t]*([。.!！?？])", r"\1", text)
    text = re.sub(r"[ \t]+([，。！？；、])", r"\1", text)
    text = re.sub(r"(?m)^[ \t]*[,，、;；]+[ \t]*", "", text)
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text).strip()
    for index, value in enumerate(protected):
        text = text.replace(f"{prefix}{index}\ue001", value)
    return text
