"""Concurrent generation with one cancellable queue for paced publication.

Transport and storage are local fakes. The timing tests exercise Engine's real
wait method with a controllable Event.wait rather than sleeping between replies.
"""
import copy
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import patch

from backend import rooms
from backend.engine import Engine, Run
from backend.scenes import current_scene
from backend.skills import SkillStore
from backend.store import Store
from tests.test_features import ObservedEngine, context, decision
from tests.test_wangsheng_engine import Gateway


class ControlledTimingEngine(ObservedEngine):
    """Keep the production delay calculation/state path, control only time."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending = queue.Queue()

    def _wait_for_reply(self, run, provider):
        gate = threading.Event()

        def wait(delay):
            self.pending.put((run, provider, delay, gate))
            if not gate.wait(3):
                raise RuntimeError("timing test did not release reply")
            return run.cancel.is_set()

        with patch.object(run.cancel, "wait", side_effect=wait):
            return Engine._wait_for_reply(self, run, provider)


class ConcurrentDialogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "history")
        self.events = []
        self.event_condition = threading.Condition()

    def emit(self, event, payload):
        with self.event_condition:
            self.events.append((event, payload))
            self.event_condition.notify_all()

    def wait_state(self, cid, provider, state):
        with self.event_condition:
            return self.event_condition.wait_for(lambda: any(
                e == "state" and p["conversationId"] == cid and p["providers"].get(provider) == state
                for e, p in self.events), timeout=2)

    def engine(self, callback=None, timed=False, skills=None):
        gateway = Gateway(callback)
        cls = ControlledTimingEngine if timed else ObservedEngine
        engine = cls(self.store, gateway, self.emit, skills=skills)
        self.addCleanup(engine.stop_all)
        return engine, gateway

    def finish(self, engine, result, cid):
        self.assertTrue(engine.wait_finished(result), "conversation did not finish")
        messages = self.store.get(cid)["messages"]
        self.assertFalse([m for m in messages if m.get("kind") == "error"], messages)
        return messages

    def test_all_current_and_future_rooms_generate_concurrently_from_one_snapshot_per_round(self):
        future = copy.deepcopy(rooms.get_room("zzz-trio"))
        future.update(id="future-dialogue-room", name="Future room")
        # Guest frequency is covered separately; this exercises every role's
        # concurrent transport and per-round snapshot, including optional guests.
        with patch.dict(rooms._ROOMS, {future["id"]: future}), \
                patch("backend.protagonists.eligible_guests", side_effect=lambda conversation, members, number: set(members)):
            for room_id in rooms._ROOMS:
                with self.subTest(room=room_id):
                    room = rooms.get_room(room_id)
                    members = list(reversed(room["characters"]))
                    cid = self.store.create(room_id)["id"]
                    barrier = threading.Barrier(len(members))

                    def respond(room, slot, prompt, cancel):
                        previous = [m["speaker"] for m in context(prompt) if m["speaker"] != "user"]
                        barrier.wait(timeout=2)
                        if not previous:
                            self.assertEqual([m["speaker"] for m in context(prompt)], ["user"])
                            return decision("第一轮-" + slot)
                        self.assertEqual(set(previous), set(members))
                        self.assertEqual(len(previous), len(members))
                        published = [p["message"]["provider"] for e, p in self.events
                                     if e == "message" and p["conversationId"] == cid and p["message"]["role"] == "assistant"]
                        self.assertEqual(set(published), set(members))
                        return decision()

                    engine, gateway = self.engine(respond)
                    result = engine.start(cid, "一起坐坐", {"participants": members, "maxRounds": 2, "webSearch": "off"})
                    messages = self.finish(engine, result, cid)
                    self.assertEqual(len(gateway.calls), 2 * len(members))
                    self.assertEqual({call[1] for call in gateway.calls[:len(members)]}, set(members))
                    self.assertEqual({m["provider"] for m in messages if m["role"] == "assistant"}, set(members))
                    first_context = context(gateway.calls[0][2])
                    self.assertTrue(all(context(call[2]) == first_context for call in gateway.calls[:len(members)]))

    def test_private_turns_keep_saved_character_skill_and_absent_roles_uninformed(self):
        skills = SkillStore(Path(self.temp.name) / "skills")
        skills.update("gemini", "PRIVATE_STYLE: 喜欢把问题说得简洁")
        cid = self.store.create("zzz-trio")["id"]

        def respond(room, slot, prompt, cancel):
            self.assertIn("PRIVATE_STYLE", prompt)
            self.assertIn("PRIVATE_TOPIC", prompt)
            self.assertIn("你只扮演千夏", prompt)
            return decision("好，我们慢慢聊。")

        engine, gateway = self.engine(respond, skills=skills)
        result = engine.start(cid, "/私聊 千夏 | PRIVATE_TOPIC", {"maxRounds": 1, "webSearch": "off"})
        messages = self.finish(engine, result, cid)
        self.assertEqual([call[1] for call in gateway.calls], ["gemini"])
        self.assertEqual(current_scene(self.store.get(cid))["audience"], ["user", "gemini"])
        self.assertEqual([m["provider"] for m in messages if m["role"] == "assistant"], ["gemini"])

    def test_completion_order_queue_publishes_fast_reply_before_slow_first_member(self):
        cid = self.store.create("standard")["id"]
        members = ["deepseek", "gemini", "gpt"]
        barrier = threading.Barrier(3)
        release = {p: threading.Event() for p in members[:2]}
        for gate in release.values():
            self.addCleanup(gate.set)

        def respond(room, slot, prompt, cancel):
            self.assertEqual([m["speaker"] for m in context(prompt)], ["user"])
            barrier.wait(timeout=2)
            if slot in release:
                self.assertTrue(release[slot].wait(3), "model completion gate was not released")
            return decision("回复-" + slot)

        engine, gateway = self.engine(respond, timed=True)
        result = engine.start(cid, "大家好", {"participants": members, "maxRounds": 1, "webSearch": "off"})
        for index, expected in enumerate(("gpt", "gemini", "deepseek")):
            run, provider, delay, gate = engine.pending.get(timeout=2)
            self.addCleanup(gate.set)
            self.assertEqual(provider, expected)
            self.assertGreaterEqual(delay, 1.2)
            self.assertLessEqual(delay, 2.8)
            self.assertEqual({call[1] for call in gateway.calls}, set(members))
            stored = [m for m in self.store.get(cid)["messages"] if m["role"] == "assistant"]
            emitted = [p for e, p in self.events if e == "message" and p["message"]["role"] == "assistant"]
            self.assertEqual(len(stored), index)
            self.assertEqual(len(emitted), index)
            self.assertEqual(engine.state_snapshot()[cid]["providers"][provider], "typing")
            self.assertTrue(engine.pending.empty(), "more than one reply is waiting for publication at once")
            if index < 2:
                following = ("gemini", "deepseek")[index]
                release[following].set()
                self.assertTrue(self.wait_state(cid, following, "queued"))
                self.assertEqual(engine.state_snapshot()[cid]["providers"][provider], "typing")
            gate.set()
        messages = self.finish(engine, result, cid)
        self.assertEqual([m["provider"] for m in messages if m["role"] == "assistant"], ["gpt", "gemini", "deepseek"])
        states = [p["providers"] for e, p in self.events if e == "state" and p["status"] == "running"]
        for provider in members:
            changes = [state.get(provider) for state in states]
            positions = [changes.index(value) for value in ("thinking", "queued", "typing", "speaking")]
            self.assertEqual(positions, sorted(positions))

    def test_stopping_or_switching_scene_discards_all_unpublished_replies(self):
        for action in ("stop", "scene"):
            with self.subTest(action=action):
                cid = self.store.create("standard")["id"]
                barrier = threading.Barrier(3)

                def respond(room, slot, prompt, cancel):
                    barrier.wait(timeout=2)
                    return decision("未发布-" + slot)

                engine, _ = self.engine(respond, timed=True)
                result = engine.start(cid, "旧问题", {"participants": ["deepseek", "gpt", "gemini"], "maxRounds": 1, "webSearch": "off"})
                run, _, _, gate = engine.pending.get(timeout=2)
                self.addCleanup(gate.set)
                for provider in ("deepseek", "gpt", "gemini"):
                    self.assertTrue(self.wait_state(cid, provider, "queued"))
                if action == "scene":
                    engine.start(cid, "/私聊 Gemini")
                else:
                    self.assertTrue(engine.stop(result["runId"]))
                count = len(self.events)
                gate.set()
                messages = self.finish(engine, result, cid)
                self.assertFalse(any(m["role"] == "assistant" for m in messages))
                self.assertEqual(len(self.events), count)
                self.assertTrue(run.cancel.is_set())
                self.assertTrue(engine.pending.empty())

    def test_stopping_does_not_wait_for_a_slow_generator_after_fast_reply_is_published(self):
        cid = self.store.create("standard")["id"]
        barrier = threading.Barrier(2)
        slow_release, slow_finished = threading.Event(), threading.Event()
        self.addCleanup(slow_release.set)

        def respond(room, slot, prompt, cancel):
            barrier.wait(timeout=2)
            if slot == "deepseek":
                slow_release.wait(3)
                slow_finished.set()
            return decision("回复-" + slot)

        engine, gateway = self.engine(respond, timed=True)
        result = engine.start(cid, "一起聊聊", {"participants": ["deepseek", "gpt"], "maxRounds": 1, "webSearch": "off"})
        _, provider, _, gate = engine.pending.get(timeout=2)
        self.addCleanup(gate.set)
        self.assertEqual(provider, "gpt")
        gate.set()
        self.assertTrue(self.wait_state(cid, "gpt", "speaking"))
        self.assertFalse(slow_finished.is_set())
        self.assertTrue(engine.stop(result["runId"]))
        self.assertTrue(engine.wait_finished(result), "cancel waited for an unfinished transport")
        self.assertFalse(slow_finished.is_set(), "run completion should not depend on the slow generator")
        count = len(self.events)
        slow_release.set()
        self.assertTrue(slow_finished.wait(1))
        self.assertEqual(len(self.events), count)
        self.assertEqual([m["provider"] for m in self.store.get(cid)["messages"] if m["role"] == "assistant"], ["gpt"])

    def test_replacement_run_discards_old_pending_reply_and_publishes_only_new(self):
        cid = self.store.create("standard")["id"]
        barrier = threading.Barrier(3)

        def respond(room, slot, prompt, cancel):
            text = context(prompt)[-1]["content"]
            if text == "旧问题":
                barrier.wait(timeout=2)
            return decision(text + "的回答")

        engine, gateway = self.engine(respond, timed=True)
        old = engine.start(cid, "旧问题", {"participants": ["deepseek", "gpt", "gemini"], "maxRounds": 1, "webSearch": "off"})
        _, _, _, old_gate = engine.pending.get(timeout=2)
        self.addCleanup(old_gate.set)
        for provider in ("deepseek", "gpt", "gemini"):
            self.assertTrue(self.wait_state(cid, provider, "queued"))
        new = engine.start(cid, "新问题", {"participants": ["gpt"]})
        _, _, _, new_gate = engine.pending.get(timeout=2)
        self.addCleanup(new_gate.set)
        count = len(self.events)
        old_gate.set()
        self.assertTrue(engine.wait_finished(old))
        self.assertEqual(engine.snapshot()[cid], new["runId"])
        self.assertEqual(len(self.events), count)
        new_gate.set()
        messages = self.finish(engine, new, cid)
        self.assertEqual([m["content"] for m in messages if m["role"] == "assistant"], ["新问题的回答"])

    def test_pass_and_error_do_not_schedule_a_publication_delay(self):
        def respond(room, slot, prompt, cancel):
            if slot == "gpt":
                raise ValueError("测试模型不可用")
            return decision()

        cid = self.store.create("standard")["id"]
        engine, gateway = self.engine(respond, timed=True)
        result = engine.start(cid, "大家好", {"participants": ["gpt", "gemini"], "maxRounds": 1, "webSearch": "off"})
        self.assertTrue(engine.wait_finished(result))
        self.assertTrue(engine.pending.empty())
        self.assertEqual({call[1] for call in gateway.calls}, {"gpt", "gemini"})
        messages = self.store.get(cid)["messages"]
        self.assertEqual(len([m for m in messages if m.get("kind") == "error"]), 1)
        self.assertFalse(any(m["role"] == "assistant" for m in messages))

    def test_production_wait_wakes_immediately_when_cancelled(self):
        cid = self.store.create("standard")["id"]
        entered, finished = threading.Event(), threading.Event()
        run = Run("test-run", cid)
        engine = Engine(self.store, Gateway(), lambda e, p: entered.set() if p.get("providers", {}).get("gpt") == "typing" else None)
        engine.active[cid] = run
        results = []

        def wait():
            results.append(engine._wait_for_reply(run, "gpt"))
            finished.set()

        worker = threading.Thread(target=wait, daemon=True)
        worker.start()
        self.addCleanup(run.cancel.set)
        self.assertTrue(entered.wait(1))
        run.cancel.set()
        self.assertTrue(finished.wait(.5), "reply wait ignored cancellation")
        worker.join(timeout=.5)
        self.assertEqual(results, [False])


if __name__ == "__main__":
    unittest.main()
