import json
import threading
import time
import unittest

from backend.providers import GatewayError
from backend.rooms import public_rooms
from backend.starters import StarterGenerator


FIRST = "我想把家里闲置的纸箱变成一个能长期使用的小物件，预算只有二十元，也不想准备复杂工具。请你们从实用性、制作难度和以后是否容易收纳三个角度一起想想，给我一个这周末就能尝试的方向，也欢迎互相补充不同看法。"
SECOND = "我最近想把桌面整理成一个可以随时开始阅读的小角落，但可用空间只有半张书桌，还需要保留放电脑的位置。请你们一起讨论应该先调整灯光、物品位置还是阅读流程，并说说各自方案可能遇到的问题，让我先做一个小实验。"
THIRD = "大家好，我想来休息室和你们一起聊聊今天听到的有趣声音。我注意到雨点落在不同东西上的节奏很不一样，如果把其中一种放进一段轻快的旋律，你们会从哪里开始？也可以说说想配怎样的歌词和舞台氛围，我们慢慢聊。"


def reply(content, speak=True):
    return json.dumps({"speak": speak, "to": "everyone", "content": content}, ensure_ascii=False)


class FakeGateway:
    def __init__(self, results=None, configured=("deepseek", "gpt", "gemini")):
        self.results = list(results if results is not None else [reply(FIRST)])
        self.configured = configured
        self.calls = []

    def status(self):
        return [{"id": provider, "configured": True} for provider in self.configured]

    def respond(self, provider, prompt, cancel):
        self.calls.append((provider, prompt, cancel))
        result = self.results.pop(0) if self.results else reply(FIRST)
        if isinstance(result, Exception):
            raise result
        return result


class StarterTests(unittest.TestCase):
    def test_catalog_has_stable_ids_icons_and_no_fixed_prompts(self):
        expected = {
            "zzz-roscaelifer": [("tea", "teacup"), ("invention", "mechanism"), ("skywalk", "skyline")],
            "zzz-outer-ring": [("special", "soda"), ("roadtrip", "wheel"), ("campfire", "flame")],
            "zzz-mockingbird": [("parasol", "parasol"), ("calling-card", "calling-card"), ("roses", "rose")],
            "zzz-obol": [("offduty", "coffee"), ("workshop", "settings"), ("supper", "sun")],
            "zzz-yunkui": [("tea", "coffee"), ("practice", "compass"), ("supper", "sun")],"standard": [("ideas", "lightbulb"), ("learn", "book"), ("compare", "compare")],
                    "zzz-trio": [("meet", "coffee"), ("song", "music"), ("dayoff", "sun")],
                    "wangsheng-trio": [("meet", "coffee"), ("song", "book"), ("dayoff", "sun")],
                    "zzz-krampus": [("meet", "phone"), ("case", "book"), ("dayoff", "sun")]}
        for room in public_rooms():
            self.assertEqual([(item["id"], item["icon"]) for item in room["starters"]], expected[room["id"]])
            self.assertTrue(all("prompt" not in item for item in room["starters"]))

    def test_valid_generation_prefers_gemini_and_uses_keywords(self):
        gateway = FakeGateway()
        result = StarterGenerator(gateway).generate("standard", "ideas")
        self.assertEqual(result, {"roomId": "standard", "starterId": "ideas", "provider": "gemini", "prompt": FIRST})
        prompt = gateway.calls[0][1]
        self.assertIn("讨论想法", prompt)
        self.assertIn("从不同角度分析一个问题。", prompt)
        self.assertIn('<conversation_data>\n[]\n</conversation_data>', prompt)

    def test_two_successive_results_differ_and_previous_candidate_is_excluded(self):
        gateway = FakeGateway([reply(FIRST), reply(SECOND)])
        generator = StarterGenerator(gateway)
        first = generator.generate("standard", "ideas")
        second = generator.generate("standard", "ideas")
        self.assertNotEqual(first["prompt"], second["prompt"])
        self.assertIn(FIRST, gateway.calls[1][1])
        self.assertNotEqual(gateway.calls[0][1], gateway.calls[1][1])

    def test_repeated_results_fail_without_disguising_them_as_new(self):
        gateway = FakeGateway([reply(FIRST)] * 4, configured=("gemini",))
        generator = StarterGenerator(gateway)
        generator.generate("standard", "ideas")
        with self.assertRaisesRegex(GatewayError, "不同"):
            generator.generate("standard", "ideas")
        self.assertEqual(len(gateway.calls), 4)

    def test_punctuation_only_change_is_still_a_duplicate(self):
        gateway = FakeGateway([reply(FIRST), reply(FIRST.replace("，", " "))], configured=("gemini",))
        generator = StarterGenerator(gateway, max_attempts=1)
        generator.generate("standard", "ideas")
        with self.assertRaisesRegex(GatewayError, "不同"):
            generator.generate("standard", "ideas")

    def test_failed_gemini_falls_back_to_deepseek(self):
        gateway = FakeGateway([GatewayError("secret must not appear"), reply(SECOND)])
        result = StarterGenerator(gateway).generate("standard", "learn")
        self.assertEqual(result["provider"], "deepseek")
        self.assertEqual([call[0] for call in gateway.calls], ["gemini", "deepseek"])

    def test_can_use_existing_gpt_connection(self):
        gateway = FakeGateway(configured=("gpt",))
        result = StarterGenerator(gateway).generate("standard", "compare")
        self.assertEqual(result["provider"], "gpt")

    def test_grok_only_connection_can_generate_opening_message(self):
        gateway = FakeGateway(configured=("grok",))
        result = StarterGenerator(gateway).generate("standard", "ideas")
        self.assertEqual(result["provider"], "grok")
        self.assertIn("Grok", gateway.calls[0][1])

    def test_errors_are_safe_and_attempts_are_bounded(self):
        gateway = FakeGateway([RuntimeError("SECRET local path and key")] * 5)
        with self.assertRaises(GatewayError) as caught:
            StarterGenerator(gateway).generate("standard", "ideas")
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertEqual(len(gateway.calls), 3)

    def test_invalid_room_or_theme_makes_no_model_call(self):
        gateway = FakeGateway()
        generator = StarterGenerator(gateway)
        for room, theme in (("missing", "ideas"), ("standard", "song"), ("zzz-trio", "ideas"), ("standard", None)):
            with self.subTest(room=room, theme=theme), self.assertRaises(ValueError):
                generator.generate(room, theme)
        self.assertEqual(gateway.calls, [])

    def test_unconnected_provider_state_is_reported(self):
        gateway = FakeGateway(configured=())
        with self.assertRaisesRegex(GatewayError, "尚未连接"):
            StarterGenerator(gateway).generate("standard", "ideas")
        self.assertEqual(gateway.calls, [])

    def test_rooms_and_themes_do_not_share_recent_history(self):
        gateway = FakeGateway([reply(FIRST), reply(THIRD), reply(SECOND)])
        generator = StarterGenerator(gateway)
        generator.generate("standard", "ideas")
        generator.generate("zzz-trio", "song")
        generator.generate("standard", "compare")
        self.assertNotIn(FIRST, gateway.calls[1][1])
        self.assertNotIn(FIRST, gateway.calls[2][1])
        self.assertNotIn(THIRD, gateway.calls[2][1])
        self.assertIn("千夏、南宫羽、爱芮", gateway.calls[1][1])
        self.assertNotIn("千夏", gateway.calls[0][1])

    def test_invalid_model_json_and_silence_are_not_accepted(self):
        gateway = FakeGateway(["not json", reply("", speak=False), reply(SECOND)])
        result = StarterGenerator(gateway).generate("standard", "ideas")
        self.assertEqual(result["prompt"], SECOND)
        self.assertEqual(len(gateway.calls), 3)

    def test_character_reply_is_not_returned_as_a_user_opener(self):
        gateway = FakeGateway([reply("千夏：" + THIRD), reply(THIRD)])
        self.assertEqual(StarterGenerator(gateway).generate("zzz-trio", "song")["prompt"], THIRD)
        self.assertEqual(len(gateway.calls), 2)

    def test_cancellation_timeout_releases_the_slot(self):
        gateway = FakeGateway()
        def wait_for_cancel(provider, prompt, cancel):
            self.assertTrue(cancel.wait(1))
            raise GatewayError("private timeout")
        gateway.respond = wait_for_cancel
        generator = StarterGenerator(gateway, timeout=0.08, attempt_timeout=0.03)
        start = time.monotonic()
        with self.assertRaisesRegex(GatewayError, "超时"):
            generator.generate("standard", "ideas")
        self.assertLess(time.monotonic() - start, 1)
        gateway.respond = lambda provider, prompt, cancel: reply(SECOND)
        self.assertEqual(generator.generate("standard", "ideas")["prompt"], SECOND)

    def test_busy_requests_are_rejected_without_queueing(self):
        started, release = threading.Event(), threading.Event()
        gateway = FakeGateway()
        def blocked(provider, prompt, cancel):
            started.set()
            release.wait(2)
            return reply(FIRST)
        gateway.respond = blocked
        generator = StarterGenerator(gateway, max_concurrent=1)
        results = []
        worker = threading.Thread(target=lambda: results.append(generator.generate("standard", "ideas")))
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            with self.assertRaisesRegex(GatewayError, "正在生成"):
                generator.generate("zzz-trio", "song")
        finally:
            release.set()
            worker.join(2)
        self.assertEqual(len(results), 1)

    def test_shutdown_cancels_inflight_work_and_does_not_start_fallback(self):
        started = threading.Event()
        gateway = FakeGateway()
        calls, errors = [], []
        def blocked(provider, prompt, cancel):
            calls.append(provider)
            started.set()
            cancel.wait(2)
            raise GatewayError("stopped")
        gateway.respond = blocked
        generator = StarterGenerator(gateway)
        def run():
            try:
                generator.generate("standard", "ideas")
            except GatewayError as error:
                errors.append(str(error))
        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(started.wait(1))
        generator.cancel_all()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(calls, ["gemini"])
        self.assertEqual(len(errors), 1)
        self.assertIn("停止", errors[0])
        with self.assertRaisesRegex(GatewayError, "停止"):
            generator.generate("zzz-trio", "meet")
        self.assertEqual(generator._active, set())


if __name__ == "__main__":
    unittest.main()
