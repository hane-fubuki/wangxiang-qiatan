"""Behavioral tests for bounded model conversations and durable local history."""
import json
from pathlib import Path
import tempfile
import threading
import unittest

from backend.engine import Engine, parse_decision, build_prompt
from backend.store import Store, make_message, validate_settings


def decision(content="", target="everyone"):
    return json.dumps({"speak": bool(content), "content": content, "to": target})


def context(prompt):
    return json.loads(prompt.split("<conversation_data>\n", 1)[1].split("\n</conversation_data>", 1)[0])


class FakeGateway:
    def __init__(self, respond=None, members=("deepseek", "gemini")):
        self.callback = respond or (lambda provider, prompt, cancel, count: decision())
        self.members = members
        self.calls = []
        self.condition = threading.Condition()

    def status(self):
        return [{"id": name, "name": name, "configured": True} for name in self.members]

    def respond(self, provider, prompt, cancel):
        with self.condition:
            count = 1 + sum(call[0] == provider for call in self.calls)
            self.calls.append((provider, prompt, cancel))
            self.condition.notify_all()
        return self.callback(provider, prompt, cancel, count)

    def wait_calls(self, count):
        with self.condition:
            return self.condition.wait_for(lambda: len(self.calls) >= count, timeout=4)


class ObservedEngine(Engine):
    """Record worker completion so cancellation assertions need no timing sleeps."""
    def __init__(self, *args):
        super().__init__(*args)
        self.finished = set()
        self.completion = threading.Condition()

    def _wait_for_reply(self, run, provider):
        return self._current(run)

    def _work(self, run, conversation, continued):
        try:
            super()._work(run, conversation, continued)
        finally:
            with self.completion:
                self.finished.add(run.id)
                self.completion.notify_all()

    def wait_finished(self, run_id):
        with self.completion:
            return self.completion.wait_for(lambda: run_id in self.finished, timeout=4)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.cid = self.store.create()["id"]
        self.store.update(self.cid, {"settings": {"participants": ["deepseek", "gemini"]}})
        self.events = []

    def engine(self, callback=None):
        gateway = FakeGateway(callback)
        engine = ObservedEngine(self.store, gateway, lambda event, payload: self.events.append((event, payload)))
        self.addCleanup(engine.stop_all)
        return engine, gateway

    def finish(self, engine, result):
        self.assertTrue(engine.wait_finished(result["runId"]), "conversation worker did not finish")
        return self.store.get(self.cid)["messages"]

    def final_reason(self):
        return [payload["reason"] for event, payload in self.events if event == "state" and payload["status"] == "idle"][-1]

    def test_models_generate_concurrently_from_one_round_snapshot(self):
        barrier = threading.Barrier(2)

        def respond(provider, prompt, cancel, count):
            if count == 1:
                barrier.wait(timeout=2)
                self.assertEqual([m["speaker"] for m in context(prompt)], ["user"])
                return decision(provider + " 的观点", "gemini" if provider == "deepseek" else "deepseek")
            return decision()

        engine, gateway = self.engine(respond)
        messages = self.finish(engine, engine.start(self.cid, "讨论这个问题"))
        self.assertEqual(len(gateway.calls), 4)
        first_contexts = [context(prompt) for _, prompt, _ in gateway.calls[:2]]
        self.assertEqual([item["speaker"] for item in first_contexts[0]], ["user"])
        self.assertEqual(first_contexts[0], first_contexts[1])
        for _, prompt, _ in gateway.calls[2:]:
            self.assertEqual({item["speaker"] for item in context(prompt)}, {"user", "deepseek", "gemini"})
        self.assertEqual(len([m for m in messages if m["role"] == "assistant"]), 2)
        self.assertEqual(self.final_reason(), "all_passed")

    def test_three_models_generate_concurrently_and_reply_to_gpt(self):
        members = ["deepseek", "gemini", "gpt"]
        barrier = threading.Barrier(len(members))

        def respond(provider, prompt, cancel, count):
            if count == 1:
                barrier.wait(timeout=2)
                self.assertEqual([item["speaker"] for item in context(prompt)], ["user"])
                return decision(provider + " 的观点", "gpt" if provider != "gpt" else "gemini")
            self.assertEqual({item["speaker"] for item in context(prompt)}, {"user", *members})
            return decision()

        gateway = FakeGateway(respond, members)
        engine = ObservedEngine(self.store, gateway, lambda event, payload: self.events.append((event, payload)))
        self.addCleanup(engine.stop_all)
        messages = self.finish(engine, engine.start(self.cid, "三位一起讨论", {"participants": members}))
        self.assertEqual(len(gateway.calls), 6)
        replies = [m for m in messages if m["role"] == "assistant"]
        self.assertEqual({m["provider"] for m in replies}, set(members))
        self.assertEqual({m["replyTo"] for m in replies if m["provider"] != "gpt"}, {"gpt"})
        self.assertEqual(self.final_reason(), "all_passed")

    def test_gpt_mention_requests_answer_and_identifies_codex(self):
        conversation = self.store.append(self.cid, make_message("user", "@GPT 你好"))
        conversation["settings"]["participants"].append("gpt")
        prompt = build_prompt("gpt", conversation, 1)
        self.assertIn("通过 Codex 接入的白龙娘", prompt)
        self.assertIn("是，请给出有价值的回答", prompt)
        self.assertEqual(parse_decision(decision("请补充", "gpt"))["to"], "gpt")

    def test_four_models_generate_concurrently_and_can_reply_to_grok(self):
        members = ["deepseek", "gemini", "gpt", "grok"]
        barrier = threading.Barrier(len(members))

        def respond(provider, prompt, cancel, count):
            barrier.wait(timeout=2)
            self.assertEqual([item["speaker"] for item in context(prompt)], ["user"])
            self.assertIn('"grok"', prompt)
            return decision(provider + " 的观点", "grok")

        gateway = FakeGateway(respond, members)
        engine = ObservedEngine(self.store, gateway, lambda event, payload: self.events.append((event, payload)))
        self.addCleanup(engine.stop_all)
        messages = self.finish(engine, engine.start(self.cid, "@Grok 大家一起讨论", {"participants": members, "maxRounds": 1}))
        replies = [m for m in messages if m["role"] == "assistant"]
        self.assertEqual({m["provider"] for m in replies}, set(members))
        self.assertTrue(all(m["replyTo"] == "grok" for m in replies))

    def test_character_assignments_drive_transport_but_preserve_identity_and_metadata(self):
        members = ["gemini", "deepseek", "gpt"]
        assignments = {"gemini": {"providerId": "gpt", "model": "gpt-6.1-sol"},
                       "deepseek": {"providerId": "grok", "model": "grok-4.7"}}
        calls = []

        class RoutedGateway:
            def room_status(self, room, assignments=None):
                return [{"id": slot, "configured": True,
                         **(assignments or {}).get(slot, {"providerId": slot, "model": "default-model"})}
                        for slot in members]

            def respond_for(self, room, slot, prompt, cancel, assignments=None):
                calls.append((room, slot, prompt, assignments))
                return decision(slot + " 的回答", "grok")

        cid = self.store.create("zzz-trio")["id"]
        engine = ObservedEngine(self.store, RoutedGateway(), lambda *args: None)
        self.addCleanup(engine.stop_all)
        result = engine.start(cid, "大家好", {"models": assignments, "maxRounds": 2})
        self.assertTrue(engine.wait_finished(result["runId"]))
        self.assertEqual(len(calls), 6)
        names = {"gemini": "千夏", "deepseek": "南宫羽", "gpt": "爱芮"}
        for room, slot, prompt, sent in calls:
            self.assertEqual(room, "zzz-trio")
            self.assertEqual(sent, assignments)
            self.assertIn("你只扮演" + names[slot], prompt)
        replies = {m["provider"]: m for m in self.store.get(cid)["messages"] if m["role"] == "assistant"}
        self.assertEqual(replies["gemini"]["providerId"], "gpt")
        self.assertEqual(replies["gemini"]["model"], "gpt-6.1-sol")
        self.assertEqual(replies["deepseek"]["providerId"], "grok")
        self.assertEqual(replies["deepseek"]["model"], "grok-4.7")
        self.assertTrue(all(m["replyTo"] == "everyone" for m in replies.values()), "Grok is not a trio character slot")

    def test_all_models_abstaining_ends_immediately(self):
        engine, gateway = self.engine()
        messages = self.finish(engine, engine.start(self.cid, "无需补充", {"maxRounds": 8}))
        self.assertEqual(len(gateway.calls), 2)
        self.assertEqual([m["role"] for m in messages], ["user"])
        self.assertEqual(self.final_reason(), "all_passed")

    def test_discussion_has_hard_round_bound(self):
        engine, gateway = self.engine(lambda provider, prompt, cancel, count: decision(f"{provider} 第 {count} 轮"))
        messages = self.finish(engine, engine.start(self.cid, "一直讨论", {"maxRounds": 3}))
        replies = [m for m in messages if m["role"] == "assistant"]
        self.assertEqual(len(gateway.calls), 6)
        self.assertEqual([m["round"] for m in replies], [1, 1, 2, 2, 3, 3])
        self.assertEqual(self.final_reason(), "max_rounds")

    def test_model_failure_preserves_other_response_and_does_not_leak_unknown_exception(self):
        def respond(provider, prompt, cancel, count):
            if provider == "deepseek":
                raise RuntimeError("secret-api-key-do-not-expose")
            return decision("仍可正常回答")

        engine, gateway = self.engine(respond)
        messages = self.finish(engine, engine.start(self.cid, "请回答"))
        self.assertEqual(len(gateway.calls), 2)
        self.assertTrue(any(m["role"] == "assistant" and m["provider"] == "gemini" for m in messages))
        self.assertTrue(any(m.get("kind") == "error" and m["provider"] == "deepseek" for m in messages))
        self.assertNotIn("secret-api-key", json.dumps(messages))
        self.assertEqual(self.final_reason(), "complete")

    def test_stop_signals_transport_and_discards_late_messages(self):
        release = threading.Event()
        self.addCleanup(release.set)

        def respond(provider, prompt, cancel, count):
            release.wait(timeout=3)
            return decision("迟到的回答")

        engine, gateway = self.engine(respond)
        result = engine.start(self.cid, "开始")
        self.assertTrue(gateway.wait_calls(2))
        self.assertTrue(engine.stop(result["runId"]))
        self.assertTrue(all(cancel.is_set() for _, _, cancel in gateway.calls))
        event_count_after_stop = len(self.events)
        release.set()
        messages = self.finish(engine, result)
        self.assertEqual([m["role"] for m in messages], ["user"])
        self.assertEqual(engine.snapshot(), {})
        self.assertEqual(self.final_reason(), "stopped")
        self.assertEqual(len(self.events), event_count_after_stop, "a stopped run emitted a late event")

    def test_replacement_run_is_not_removed_by_old_worker(self):
        old_release, new_release = threading.Event(), threading.Event()
        self.addCleanup(old_release.set)
        self.addCleanup(new_release.set)

        def respond(provider, prompt, cancel, count):
            if context(prompt)[-1]["content"] == "旧问题":
                old_release.wait(timeout=3)
                return decision("旧回答")
            new_release.wait(timeout=3)
            return decision("新回答 " + provider)

        engine, gateway = self.engine(respond)
        old = engine.start(self.cid, "旧问题", {"maxRounds": 1})
        self.assertTrue(gateway.wait_calls(2))
        new = engine.start(self.cid, "新问题")
        self.assertTrue(gateway.wait_calls(4))
        event_count_before_old_completion = len(self.events)
        old_release.set()
        self.assertTrue(engine.wait_finished(old["runId"]))
        self.assertEqual(engine.snapshot().get(self.cid), new["runId"])
        self.assertEqual(len(self.events), event_count_before_old_completion)
        new_release.set()
        messages = self.finish(engine, new)
        self.assertFalse(any(m["content"] == "旧回答" for m in messages))
        self.assertEqual(len([m for m in messages if m["role"] == "assistant"]), 2)

    def test_deleted_active_conversation_is_not_recreated_by_late_model_response(self):
        release = threading.Event()
        self.addCleanup(release.set)

        def respond(provider, prompt, cancel, count):
            release.wait(timeout=3)
            return decision("不能恢复已删除记录")

        engine, gateway = self.engine(respond)
        result = engine.start(self.cid, "稍后删除")
        self.assertTrue(gateway.wait_calls(2))
        # This is the same lock boundary used by DELETE /api/conversations/:id.
        with engine.lock:
            engine.stop_conversation(self.cid)
            self.store.delete(self.cid)
        event_count_after_delete = len(self.events)
        release.set()
        self.assertTrue(engine.wait_finished(result["runId"]))
        self.assertEqual(self.store.list(), [])
        self.assertEqual(Store(self.temp.name).list(), [])
        self.assertEqual(engine.snapshot(), {})
        self.assertEqual(len(self.events), event_count_after_delete)

    def test_identical_repeat_is_suppressed_and_stops_discussion(self):
        engine, gateway = self.engine(lambda provider, prompt, cancel, count: decision("同一个回答"))
        messages = self.finish(engine, engine.start(self.cid, "讨论", {"maxRounds": 8}))
        self.assertEqual(len(gateway.calls), 4)
        self.assertEqual(len([m for m in messages if m["role"] == "assistant"]), 2)
        self.assertEqual(self.final_reason(), "all_passed")

    def test_new_user_message_can_receive_the_same_answer_from_a_previous_run(self):
        engine, gateway = self.engine(lambda provider, prompt, cancel, count: decision("同一个回答"))
        first = self.finish(engine, engine.start(self.cid, "请回答一次", {"maxRounds": 8}))
        self.assertEqual(len([m for m in first if m["role"] == "assistant"]), 2)
        self.assertEqual(len(gateway.calls), 4)
        second = self.finish(engine, engine.start(self.cid, "请重复刚才的回答"))
        replies = [m for m in second if m["role"] == "assistant"]
        self.assertEqual(len(replies), 4)
        self.assertEqual([m["content"] for m in replies], ["同一个回答"] * 4)
        self.assertEqual([m["round"] for m in replies], [1, 1, 1, 1])
        # Each run admits both first-round replies, then stops their repetition.
        self.assertEqual(len(gateway.calls), 8)
        self.assertEqual(self.final_reason(), "all_passed")

    def test_invalid_decisions_are_not_rendered_as_chat(self):
        for raw in ("plain text", "[]", '{"speak":"false"}', '{"speak":true,"content":""}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_decision(raw)
        self.assertEqual(parse_decision('```json\n{"speak":false}\n```')["speak"], False)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.cid = self.store.create()["id"]

    def test_history_settings_and_deletion_survive_reload(self):
        self.store.append(self.cid, make_message("user", "中文聊天内容"))
        self.store.update(self.cid, {"title": "保留这个名称", "settings": {"maxRounds": 5}})
        restored = Store(self.temp.name)
        self.assertEqual(restored.get(self.cid), self.store.get(self.cid))
        restored.delete(self.cid)
        self.assertEqual(Store(self.temp.name).list(), [])

    def test_snapshots_cannot_mutate_saved_history(self):
        item = self.store.get(self.cid)
        item["settings"]["participants"].clear()
        item["messages"].append({"content": "injected"})
        self.assertEqual(self.store.get(self.cid)["messages"], [])
        self.assertEqual(len(self.store.get(self.cid)["settings"]["participants"]), 4)

    def test_room_specific_participants_and_model_assignments_survive_reload(self):
        route = {"gemini": {"providerId": "grok", "model": "grok-4.7"}}
        trio = self.store.create("zzz-trio")
        self.assertEqual(set(trio["settings"]["participants"]), {"gemini", "deepseek", "gpt"})
        self.store.update(trio["id"], {"settings": {"participants": ["gemini"], "models": route}})
        restored = Store(self.temp.name).get(trio["id"])
        self.assertEqual(restored["settings"]["models"], route)
        restored["settings"]["models"]["gemini"]["model"] = "mutated"
        self.assertEqual(self.store.get(trio["id"])["settings"]["models"], route)
        with self.assertRaises(ValueError):
            self.store.update(trio["id"], {"settings": {"participants": ["grok"]}})
        with self.assertRaises(ValueError):
            self.store.update(trio["id"], {"settings": {"models": {"grok": route["gemini"]}}})

    def test_unsafe_model_assignments_are_rejected(self):
        for route in (None, [], {"providerId": "other", "model": "grok-4.7"},
                      {"providerId": "grok", "model": "--command=x"},
                      {"providerId": "grok", "model": "https://untrusted.example/model"},
                      {"providerId": "grok", "model": "grok-4.7", "apiKey": "should-not-save"}):
            with self.subTest(route=route), self.assertRaises(ValueError):
                validate_settings({"models": {"grok": route}})

    def test_legacy_participation_is_not_expanded_when_reloaded(self):
        item = self.store.get(self.cid)
        item["settings"].pop("models")
        item["settings"]["participants"] = ["deepseek", "gemini", "gpt"]
        self.store.path.write_text(json.dumps({"version": 1, "conversations": [item]}), encoding="utf-8")
        restored = Store(self.temp.name)
        self.assertEqual(restored.get(self.cid), item)
        updated = restored.update(self.cid, {"settings": {"maxRounds": 4}})
        self.assertEqual(updated["settings"]["participants"], item["settings"]["participants"])
        self.assertEqual(updated["settings"]["models"], {})

    def test_invalid_update_is_atomic_in_memory_and_on_disk(self):
        before = self.store.get(self.cid)
        with self.assertRaises(ValueError):
            self.store.update(self.cid, {"settings": {"maxRounds": 8}, "title": ""})
        self.assertEqual(self.store.get(self.cid), before)
        self.assertEqual(Store(self.temp.name).get(self.cid), before)

    def test_invalid_storage_is_preserved(self):
        path = Path(self.temp.name) / "conversations.json"
        path.write_text("not valid json", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            Store(self.temp.name)
        self.assertEqual(path.read_text(encoding="utf-8"), "not valid json")


if __name__ == "__main__":
    unittest.main()
