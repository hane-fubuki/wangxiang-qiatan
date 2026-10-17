"""Behavioral checks for shared research, unknown terms, and bounded retries."""
import json
import tempfile
import threading
import unittest

from backend.engine import build_prompt, parse_decision
from backend.reasoning import reasoning_effort, should_search, research_prompt
from backend.store import Store, make_message
from tests.test_features import ObservedEngine, RoutedGateway, decision, context


class FakeResearch:
    def __init__(self, callback=None):
        self.calls = []
        self.callback = callback

    def status(self):
        return {"configured": True}

    def search(self, prompt, cancel, **options):
        self.calls.append((prompt, options))
        if self.callback:
            return self.callback(prompt, cancel)
        return {"summary": "公开来源确认：测试术语是一个合成示例。", "sources": [
            {"title": "官方说明", "url": "https://www.python.org/downloads/"}], "elapsedMs": 50}


class ReasoningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.cid = self.store.create("zzz-trio")["id"]
        self.events = []

    def conversation(self, text, **settings):
        conversation = self.store.get(self.cid)
        # Prompt-only fixtures below construct legacy messages by hand.
        conversation["identityEpoch"] = "legacy"
        conversation["messages"] = [make_message("user", text)]
        conversation["settings"].update(settings)
        return conversation

    def engine(self, callback=None, research=None):
        gateway = RoutedGateway(callback)
        engine = ObservedEngine(self.store, gateway, lambda event, data: self.events.append((event, data)),
                                research=research or FakeResearch())
        self.addCleanup(engine.stop_all)
        return engine, gateway

    def finish(self, engine, content, settings=None):
        result = engine.start(self.cid, content, {"maxRounds": 1, **(settings or {})})
        self.assertTrue(engine.wait_finished(result))
        return self.store.get(self.cid)["messages"]

    def test_policy_catches_terms_freshness_and_respects_local_setting(self):
        for text in ("伊埃斯是什么？", "帮我查一下近期更新", "绝区零的官方世界观", "Python现在最新版本是多少？"):
            self.assertTrue(should_search(self.conversation(text)), text)
        for text in ("千夏，你最喜欢什么颜色？", "今天一起喝茶吧", "我自创的设定是什么样都可以", "不要联网，解释这个术语",
                     "别查资料，聊聊背景设定", "不用查资料，解释这个术语", "不允许联网，请解释设定", "这张图的小字是什么颜色"):
            self.assertFalse(should_search(self.conversation(text)), text)
        self.assertFalse(should_search(self.conversation("联网查Python官网", webSearch="off")))
        self.assertTrue(should_search(self.conversation("整理一个话题", webSearch="always")))
        self.assertEqual(reasoning_effort(self.conversation("认真思考其中的逻辑矛盾")), "high")
        self.assertEqual(reasoning_effort(self.conversation("你好")), "medium")
        self.assertEqual(reasoning_effort(self.conversation("你好", reasoning="deep")), "high")

    def test_explicit_lookup_happens_once_before_all_participants(self):
        research = FakeResearch()

        def respond(room, slot, prompt, cancel):
            self.assertEqual(len(research.calls), 1)
            self.assertIn("公开来源确认", prompt)
            self.assertNotIn("https://www.python.org/downloads/", prompt)
            return decision(slot + " 根据资料回答")

        engine, gateway = self.engine(respond, research)
        messages = self.finish(engine, "查询测试术语是什么")
        self.assertEqual(len(research.calls), 1)
        self.assertEqual(len(gateway.calls), 3)
        self.assertEqual(messages[0]["webResearch"]["status"], "complete")
        self.assertEqual(messages[0]["webResearch"]["sources"][0]["url"], "https://www.python.org/downloads/")
        self.assertEqual(len([m for m in messages if m["role"] == "assistant"]), 3)
        self.assertTrue(any(d.get("research", {}).get("stage") == "searching" for e,d in self.events if e == "state"))
        self.assertEqual(self.events[-1][1]["research"], {})

    def test_research_citations_are_cleaned_before_storage_and_public_events(self):
        raw = ("刚去核实了一下，我也很期待见面（[官方说明]\n(https://www.python.org/downloads/)）。"
               "不过，还没确认会在哪里见到她。")
        engine, gateway = self.engine(lambda *args: decision(raw))
        messages = self.finish(engine, "帮我查一下这个联动，然后我们接着聊")
        answers = [m for m in messages if m["role"] == "assistant"]
        self.assertEqual(len(answers), 3)
        for answer in answers:
            self.assertNotIn("https://", answer["content"])
            self.assertNotIn("刚去核实", answer["content"])
            self.assertIn("我也很期待见面", answer["content"])
            self.assertIn("还没确认会在哪里见到她", answer["content"])
        for event, payload in self.events:
            if event == "message" and payload.get("message", {}).get("role") == "assistant":
                self.assertNotIn("https://", payload["message"]["content"])
        self.assertEqual(messages[0]["webResearch"]["sources"][0]["url"], "https://www.python.org/downloads/")

    def test_source_followup_uses_retained_evidence_and_keeps_requested_link(self):
        research = FakeResearch()
        url = "https://www.python.org/downloads/"
        def respond(room, slot, prompt, cancel):
            if "这个从哪看到的" in prompt:
                self.assertIn(url, prompt)
                return decision("这条说明在这里：[官方说明](" + url + ")")
            return decision("我们可以接着聊这个话题。")
        engine, gateway = self.engine(respond, research)
        self.finish(engine, "查询测试术语是什么")
        messages = self.finish(engine, "这个从哪看到的？")
        self.assertEqual(len(research.calls), 1)
        self.assertIn(url, messages[-1]["content"])

    def test_prompt_hides_historical_citations_without_rewriting_saved_content(self):
        conversation = self.conversation("我们接着聊吧")
        user = conversation["messages"].pop()
        source = {"title": "官方说明", "url": "https://www.python.org/downloads/"}
        prior = make_message("user", "查询一个术语")
        prior["webResearch"] = {"status": "complete", "summary": "事实说明[1]。", "sources": [source]}
        answer = make_message("assistant", "有了新消息（[官方说明](" + source["url"] + ")）。", provider="gpt")
        conversation["messages"] = [prior, answer, user]
        before = json.dumps(conversation, ensure_ascii=False)
        prompt = build_prompt("gemini", conversation, 1)
        self.assertNotIn(source["url"], prompt)
        self.assertEqual(json.dumps(conversation, ensure_ascii=False), before)

    def test_citation_only_reply_is_not_published_as_an_empty_message(self):
        engine, gateway = self.engine(lambda *args: decision("[官方说明](https://www.python.org/downloads/)"))
        messages = self.finish(engine, "查询测试术语是什么")
        self.assertFalse(any(m["role"] == "assistant" for m in messages))

    def test_parallel_unknown_term_requests_share_one_research_result_and_retry_each_requester(self):
        research = FakeResearch()
        barrier = threading.Barrier(3)
        counts = {}
        lock = threading.Lock()

        def respond(room, slot, prompt, cancel):
            with lock:
                counts[slot] = counts.get(slot, 0) + 1
                count = counts[slot]
            self.assertEqual([m["speaker"] for m in context(prompt)], ["user"])
            if count == 1:
                barrier.wait(timeout=2)
                return json.dumps({"speak": True, "content": "尚未核实的初稿，不应展示", "to": "user", "searchQuery": "某作品 未知术语"})
            self.assertIn("公开来源确认", prompt)
            return decision(slot + " 核实后的回答")

        engine, gateway = self.engine(respond, research)
        messages = self.finish(engine, "我们聊聊某个陌生的名称")
        self.assertEqual(len(research.calls), 1)
        self.assertEqual(counts, {"gemini": 2, "deepseek": 2, "gpt": 2})
        self.assertEqual(len(gateway.calls), 6)
        self.assertFalse(any("初稿" in m["content"] for m in messages))
        self.assertIn("某作品 未知术语", research.calls[0][0])

    def test_slow_research_does_not_block_ready_reply_or_add_it_to_retry_snapshot(self):
        research_started, ready_published = threading.Event(), threading.Event()
        barrier = threading.Barrier(3)
        counts = {}
        lock = threading.Lock()

        def search(prompt, cancel):
            research_started.set()
            self.assertTrue(ready_published.wait(2), "research blocked an already completed reply")
            return {"summary": "独立证据", "sources": [{"title": "示例资料", "url": "https://www.python.org/"}], "elapsedMs": 1}

        def respond(room, slot, prompt, cancel):
            with lock:
                counts[slot] = counts.get(slot, 0) + 1
                count = counts[slot]
            if count == 1:
                barrier.wait(timeout=2)
                if slot == "gemini":
                    return json.dumps({"speak": False, "searchQuery": "一个未知名称"})
                self.assertTrue(research_started.wait(2))
                return decision("我先聊已经知道的部分。" if slot == "gpt" else "")
            self.assertTrue(ready_published.is_set())
            self.assertEqual([m["speaker"] for m in context(prompt)], ["user"])
            self.assertIn("独立证据", prompt)
            return decision("这个名称我明白了。")

        research = FakeResearch(search)
        engine, gateway = self.engine(respond, research)
        original_emit = engine.emit

        def emit(event, payload):
            original_emit(event, payload)
            if event == "message" and payload["message"].get("provider") == "gpt":
                ready_published.set()

        engine.emit = emit
        messages = self.finish(engine, "我们随便聊聊")
        self.assertEqual(len(research.calls), 1)
        self.assertEqual(counts, {"gemini": 2, "deepseek": 1, "gpt": 1})
        self.assertEqual([m["provider"] for m in messages if m["role"] == "assistant"], ["gpt", "gemini"])

    def test_failed_search_is_recorded_and_does_not_invent_source_or_retry(self):
        def fail(*args):
            raise RuntimeError("secret upstream text")

        research = FakeResearch(fail)
        engine, gateway = self.engine(lambda *args: decision("尚未核实，无法确认"), research)
        messages = self.finish(engine, "查一下这个设定")
        self.assertEqual(messages[0]["webResearch"]["status"], "failed")
        self.assertNotIn("secret upstream text", json.dumps(messages))
        result = engine.start(self.cid)
        self.assertTrue(engine.wait_finished(result))
        self.assertEqual(len(research.calls), 1)

    def test_unknown_term_lookup_is_bounded_even_if_model_keeps_requesting(self):
        research = FakeResearch()
        request = json.dumps({"speak": False, "to": "user", "content": "", "searchQuery": "未知名词"})
        engine, gateway = self.engine(lambda *args: request, research)
        messages = self.finish(engine, "我们聊聊某名称")
        self.assertEqual(len(research.calls), 1)
        self.assertEqual(len(gateway.calls), 6)
        self.assertTrue(any("没有核实清楚" in m["content"] for m in messages))

    def test_web_off_does_not_execute_a_model_lookup(self):
        research = FakeResearch()
        request = json.dumps({"speak": True, "to": "user", "content": "编造的初稿", "searchQuery": "未知名词"})
        engine, gateway = self.engine(lambda *args: request, research)
        messages = self.finish(engine, "聊聊这个名称", {"webSearch": "off"})
        self.assertEqual(research.calls, [])
        self.assertFalse(any("编造" in m["content"] for m in messages))

    def test_cancellation_prevents_late_search_result_and_answer(self):
        entered, release = threading.Event(), threading.Event()

        def blocked(prompt, cancel):
            entered.set()
            release.wait(timeout=4)
            return {"summary": "迟到资料", "sources": [{"title": "官网", "url": "https://www.python.org/"}]}

        research = FakeResearch(blocked)
        engine, gateway = self.engine(research=research)
        result = engine.start(self.cid, "查一下最新资料")
        self.assertTrue(entered.wait(timeout=2))
        engine.stop(result["runId"])
        release.set()
        self.assertTrue(engine.wait_finished(result))
        messages = self.store.get(self.cid)["messages"]
        self.assertEqual(len(messages), 1)
        self.assertNotIn("webResearch", messages[0])
        self.assertEqual(gateway.calls, [])

    def test_reasoning_option_reaches_selected_model_without_changing_identity(self):
        engine, gateway = self.engine(lambda *args: decision("ok"))
        gateway.supports_reasoning_options = True
        efforts = []
        original = gateway.respond_for

        def respond(room, slot, prompt, cancel, **options):
            efforts.append(options["reasoning_effort"])
            return original(room, slot, prompt, cancel)

        gateway.respond_for = respond
        self.finish(engine, "分析其中的逻辑", {"webSearch": "off"})
        self.assertEqual(efforts, ["high"] * 3)

    def test_legacy_decision_stays_compatible_and_search_has_no_draft(self):
        self.assertEqual(parse_decision(decision("你好")), {"speak": True, "to": "user", "content": "你好"})
        result = parse_decision(json.dumps({"speak": True, "to": "user", "content": "未核实", "searchQuery": "名词"}))
        self.assertFalse(result["speak"])
        self.assertEqual(result["content"], "")
        with self.assertRaises(ValueError):
            parse_decision('{"speak":false,"searchQuery":{}}')

    def test_current_question_and_evidence_survive_verbose_later_answers(self):
        conversation = self.conversation("CURRENT_QUESTION")
        conversation["messages"][0]["webResearch"] = {"status": "complete", "summary": "CURRENT_EVIDENCE", "sources": []}
        conversation["messages"].extend(make_message("assistant", "很长的回答" * 3200, provider=p) for p in ("deepseek", "gemini", "gpt"))
        prompt = build_prompt("gemini", conversation, 2)
        items = context(prompt)
        self.assertIn("CURRENT_QUESTION", items[0]["content"])
        self.assertIn("CURRENT_EVIDENCE", items[0]["content"])
        self.assertLessEqual(sum(len(item["content"]) for item in items), 40000)

    def test_serialized_research_budget_preserves_question_tail(self):
        sentinel = "END_QUESTION_SENTINEL: 请查询这个术语的官方出处"
        conversation = self.conversation("背景资料" * 2300 + sentinel)
        self.assertIn(sentinel, research_prompt(conversation))
        for char in ('"', '\x01', '字'):
            conversation = self.conversation(char * 11900 + sentinel)
            user = conversation["messages"].pop()
            conversation["messages"] = [make_message("assistant", char * 12000, provider="gpt") for _ in range(8)] + [user]
            user["imageDescription"] = char * 12000
            prompt = research_prompt(conversation, [char * 400] * 4)
            self.assertLessEqual(len(prompt.encode("utf-8")), 23000)
            self.assertIn(sentinel, prompt)


if __name__ == "__main__":
    unittest.main()
