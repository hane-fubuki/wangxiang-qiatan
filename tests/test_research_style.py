"""Boundary tests for natural researched replies without changing their facts."""
import unittest

from backend.research_style import clean_research_reply, sources_requested


SOURCES = [
    {"title": "TapTap公告", "url": "https://www.taptap.cn/moment/857695171754593940?group_id=330333"},
    {"title": "新浪新闻", "url": "https://www.sina.cn/news/detail/5352200999535199.html"},
    {"title": "官网公告", "url": "https://zzz.mihoyo.com/news/166654"},
    {"title": "Python发行版", "url": "https://www.python.org/downloads/"},
    {"title": "嵌套路径", "url": "https://example.com/wiki/Test_(nested_(value))"},
]


class SourceRequestTests(unittest.TestCase):
    def test_explicit_requests(self):
        for text in ("出处？", "来源呢？", "把原文发我", "给我参考文献", "请列出资料来源", "官网地址是什么？",
                     "发一下下载链接", "提供 URL", "这个从哪看到的？", "你是在哪里查到的？", "原文怎么说？",
                     "Show me the sources", "Please give me a link", "Where did you read that?", "不要长清单，给我原文"):
            self.assertTrue(sources_requested(text), text)

    def test_navigation_and_one_link_without_bibliography(self):
        for text in ("怎么下载 Python？", "Python 官网在哪？", "不需要列出参考资料，只要原文链接", "发我原文，不要长串来源清单"):
            self.assertTrue(sources_requested(text), text)

    def test_lookup_is_not_source_request(self):
        for text in ("核实一下联动消息", "官方公布了吗？", "联动什么时候开始", "这个消息来源可靠吗", "根据官方公告解释一下",
                     "不要列出来源", "不用贴链接，只讲结论", "无需附参考文献", "不需要列出具体的资料/网站来源",
                     "给我结论，不要展示网址", "Please verify the announcement", "Do not show sources", "Explain without citations",
                     "这是原文中的设定", "参考资料里的版本号可靠吗？", "https://example.com/ 这是什么"):
            self.assertFalse(sources_requested(text), text)


class ResearchCleanupTests(unittest.TestCase):
    def clean(self, text):
        return clean_research_reply(text, SOURCES)

    def test_screenshot_structure_keeps_facts_and_uncertainty(self):
        text = ("刚去核实了一下，官方确实公布了联动消息，知更鸟会和卡芙卡一起来到新艾利都"
                "（[TapTap公告](https://www.taptap.cn/moment/857695171754593940?group_id=330333)、"
                "[新浪新闻](https://www.sina.cn/news/detail/5352200999535199.html)）。"
                "不过，3.4的具体日子还没定下来（[官网公告](https://zzz.mihoyo.com/news/166654)），"
                "倒还没确认她会不会来六分街。")
        self.assertEqual(self.clean(text), "官方确实公布了联动消息，知更鸟会和卡芙卡一起来到新艾利都。不过，3.4的具体日子还没定下来，倒还没确认她会不会来六分街。")

    def test_wrapped_markdown_link(self):
        self.assertEqual(self.clean("日期还没确定（[官网公告]\n(https://zzz.mihoyo.com/news/166654)）。"), "日期还没确定。")
        self.assertEqual(self.clean("日期还没确定，[官网公告]\n(https://zzz.mihoyo.com/news/166654)。"), "日期还没确定。")

    def test_nested_url_and_ascii_parentheses(self):
        self.assertEqual(self.clean("设定未确认 ([嵌套路径](https://example.com/wiki/Test_(nested_(value))))。"), "设定未确认。")
        self.assertEqual(self.clean("设定未确认 (https://example.com/wiki/Test_(nested_(value)))。"), "设定未确认。")

    def test_sources_list_and_footnotes(self):
        text = ("还不能确认。[^1]\n\n**参考资料：**\n"
                "- [官网公告](https://zzz.mihoyo.com/news/166654)\n"
                "[1]: https://www.python.org/downloads/\n"
                "[^1]: https://zzz.mihoyo.com/news/166654\n\n")
        self.assertEqual(self.clean(text), "还不能确认。")

    def test_known_bare_links_and_fragment(self):
        self.assertEqual(self.clean("消息已公布（https://zzz.mihoyo.com/news/166654#details）。"), "消息已公布。")
        self.assertEqual(self.clean("官方确认了，来源：https://zzz.mihoyo.com/news/166654。"), "官方确认了。")

    def test_unrelated_links_and_images_survive(self):
        text = ("先到[下载入口](https://downloads.example.com/app.zip)。\n"
                "![示意图](https://zzz.mihoyo.com/news/166654)\n"
                "![参考图][asset]\n[asset]: https://zzz.mihoyo.com/news/166654")
        self.assertEqual(self.clean(text), text)

    def test_code_survives_exactly(self):
        text = ("例子：`a[1] = 'https://zzz.mihoyo.com/news/166654'`\n\n"
                "```python\n# 根据检索结果，\nvalue = '[1]'\nurl = 'https://zzz.mihoyo.com/news/166654'\n```\n"
                "~~~text\n[官网公告](https://zzz.mihoyo.com/news/166654)\n~~~")
        self.assertEqual(self.clean(text), text)

    def test_numeric_citations_do_not_destroy_arrays_steps_or_vectors(self):
        text = "数组[1] 是首项。a[1] + b[2] = 3。a[1][2]。向量是 [1, 2]。请选择[1]或者[2]。第[1]项。\n[1] 先准备材料\n[2] 再开始\n1. 普通步骤\n- 普通事项"
        self.assertEqual(self.clean(text), text)
        for text in ("输入值是 [1, 2]。", "把结果记为 [1, 2]，再计算。", "把结果记为[1, 2]。", "[1, 2]", "消息已确认[1]，日期未定[1, 2]。"):
            self.assertEqual(self.clean(text), text)

    def test_qualifications_inside_known_source_links_survive(self):
        url = "https://zzz.mihoyo.com/news/166654"
        self.assertEqual(self.clean(f"活动安排在21日（[这个日期尚未得到确认]({url})）。"), "活动安排在21日（这个日期尚未得到确认）。")
        self.assertEqual(self.clean(f"但[官网尚未确认具体日期]({url})。"), "但官网尚未确认具体日期。")
        self.assertEqual(self.clean(f"[官网尚未确认具体日期]({url})"), "官网尚未确认具体日期")
        self.assertEqual(clean_research_reply(f"消息来了（[可能尚未公布]({url})）。", [{"title": "可能尚未公布", "url": url}]), "消息来了（可能尚未公布）。")

    def test_functional_known_source_links_remain_clickable(self):
        for label in ("官网下载", "打开官网", "下载 Python", "Download Python"):
            text = f"请点击[{label}](https://www.python.org/downloads/)。"
            self.assertEqual(self.clean(text), text)
            self.assertEqual(self.clean(self.clean(text)), text)

    def test_prefix_only_at_start_of_paragraph_and_uncertainty_retained(self):
        text = "根据检索结果，暂时无法确认，可能只是传闻。\n\n刚去核实了一下，没有可靠证据。"
        self.assertEqual(self.clean(text), "暂时无法确认，可能只是传闻。\n\n没有可靠证据。")
        self.assertEqual(self.clean("她说刚去核实了一下，可我仍有疑问。"), "她说刚去核实了一下，可我仍有疑问。")

    def test_meaningful_link_label_retained(self):
        self.assertEqual(self.clean("可以用 [Python 3.15](https://www.python.org/downloads/) 运行。"), "可以用 Python 3.15 运行。")
        self.assertEqual(clean_research_reply("[Python 教程](https://www.python.org/downloads/)可以帮助入门。", [{"title": "Python 教程", "url": "https://www.python.org/downloads/"}]), "Python 教程可以帮助入门。")

    def test_empty_and_idempotence(self):
        self.assertEqual(self.clean("来源：\n- [官网公告](https://zzz.mihoyo.com/news/166654)"), "")
        for text in ("刚去核实了一下，日期没定（[官网公告](https://zzz.mihoyo.com/news/166654)）。",
                     "还不能确认。[^1]\n\n来源：\n[^1]: https://zzz.mihoyo.com/news/166654",
                     "我刚查了一下，刚去核实了一下，日期未定[1][2]。",
                     "数组[1]，看[下载](https://downloads.example.com/x)。"):
            once = self.clean(text)
            self.assertEqual(self.clean(once), once)


if __name__ == "__main__":
    unittest.main()
