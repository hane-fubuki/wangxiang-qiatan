"""Question-aware image selection and shared visual evidence, without model calls."""
import json
from pathlib import Path
import tempfile
import unittest

from backend.vision_context import analysis_job, analysis_mode, analysis_prompt
from backend.store import Store, make_message
from backend.media import MediaStore
from tests.test_features import FakeMedia, ObservedEngine, RoutedGateway, context, decision, png


def message(text, *images, role="user", **extra):
    return make_message(role, text, attachments=[{"id": value, "width": 1600, "height": 1200} for value in images], **extra)


def conversation(*messages):
    return {"roomId": "zzz-trio", "messages": list(messages)}


class VisionContextTests(unittest.TestCase):
    def test_new_upload_uses_question_and_context_without_treating_it_as_pixels(self):
        chat = conversation(message("刚才谈到她左边的星形头饰"), message("看看这里是什么", "a"))
        job = analysis_job(chat)
        prompt = analysis_prompt(chat, job)
        self.assertIn("左边的星形头饰", prompt)
        self.assertIn("看看这里是什么", prompt)
        self.assertIn("旧描述、角色对白和创作要求不等于图像事实", prompt)
        self.assertEqual([a["id"] for _,a in job["sources"]], ["a"])

    def test_new_question_rereads_pixels_and_plain_continue_reuses_analysis(self):
        original = message("图里是什么", "a", imageDescription="一个人物")
        self.assertIsNone(analysis_job(conversation(original)))
        job = analysis_job(conversation(original, message("她眼睛是什么颜色？")))
        self.assertEqual(job["sources"][0][1]["id"], "a")
        for text in ("谢谢", "继续聊排练吧", "这张图很好看", "不用看图，聊聊音乐"):
            self.assertIsNone(analysis_job(conversation(original, message(text))), text)

    def test_generated_picture_is_inspected_as_real_image_on_followup(self):
        generated = message("图片已生成", "g", role="assistant", kind="image", imageDescription="创作要求：蓝发")
        chat = conversation(generated, message("这张图里实际有几个人？"))
        job = analysis_job(chat)
        self.assertEqual(job["sources"][0][1]["id"], "g")
        self.assertIn("creation_request_not_pixels", analysis_prompt(chat, job))

    def test_explicit_ordinal_selects_matching_original_and_rejects_missing(self):
        first, second = message("图A", "a", imageDescription="A"), message("图B", "b", imageDescription="B")
        chat = conversation(first, second, message("重新看第一张图的左下角是什么？"))
        self.assertEqual(analysis_job(chat)["sources"][0][1]["id"], "a")
        with self.assertRaises(ValueError):
            analysis_job(conversation(first, message("第四张图里是什么？")))

    def test_ordinal_within_latest_batch_and_compare_preserve_input_order(self):
        chat = conversation(message("旧图", "old"), message("新的一组", "a", "b", imageDescription="一组"), message("第二张图有什么？"))
        self.assertEqual(analysis_job(chat)["sources"][0][1]["id"], "b")
        chat = conversation(message("图A", "a", imageDescription="A"), message("与上一张对比有什么区别", "b"))
        self.assertEqual([a["id"] for _,a in analysis_job(chat)["sources"]], ["a", "b"])

    def test_old_unrelated_image_is_not_reopened_by_generic_question(self):
        turns = [message("头像", "a", imageDescription="头像")]+[message("普通聊天") for _ in range(9)]
        self.assertIsNone(analysis_job(conversation(*turns, message("你的头发是什么颜色？"))))
        self.assertIsNotNone(analysis_job(conversation(*turns, message("那张图片的头发是什么颜色？"))))

    def test_deep_is_opt_in_from_current_question(self):
        self.assertEqual(analysis_mode("深度分析这张图"), "deep")
        self.assertEqual(analysis_mode("用 6 Astra ultra 看这张图"), "deep")
        self.assertEqual(analysis_mode("不要深度分析，简单看图"), "auto")
        chat = conversation(message("之前用 Astra 看过"), message("现在看看这张", "a"))
        self.assertEqual(analysis_job(chat)["mode"], "auto")

    def test_context_is_bounded_and_current_question_is_preserved(self):
        chat = conversation(*[message("旧内容"*2000) for _ in range(30)], message("左上角数字是什么？", "a"))
        prompt = analysis_prompt(chat, analysis_job(chat))
        self.assertLess(len(prompt), 11000)
        self.assertIn("左上角数字是什么？", prompt)

    def test_new_upload_compares_with_explicit_old_image(self):
        chat=conversation(message("图A","a"),message("图B","b"),message("这张和第一张图相比有什么区别？","c"))
        self.assertEqual([a["id"] for _,a in analysis_job(chat)["sources"]],["a","c"])

    def test_multiple_new_uploads_compare_only_the_new_batch_unless_old_is_named(self):
        chat=conversation(message("旧图","old"),message("对比这两张的区别","a","b"))
        self.assertEqual([a["id"] for _,a in analysis_job(chat)["sources"]],["a","b"])
        with self.assertRaises(ValueError):
            analysis_job(conversation(message("旧图","old"),message("这组和上一张对比","a","b","c","d")))

    def test_followup_keeps_last_explicit_visual_focus(self):
        chat=conversation(message("图A","a"),message("图B","b"),
                          message("重新看第一张图",imageDescription="A的文字",imageAnalysis={"imageIds":["a"]}),
                          message("再看它右上角有什么？"))
        self.assertEqual([a["id"] for _,a in analysis_job(chat)["sources"]],["a"])

    def test_preferences_do_not_trigger_image_call_and_two_image_reference_does(self):
        before=[message("A","a",imageDescription="A"),message("B","b",imageDescription="B")]
        self.assertIsNone(analysis_job(conversation(*before,message("千夏，你最喜欢什么颜色？"))))
        self.assertEqual([a["id"] for _,a in analysis_job(conversation(*before,message("把刚才两张对比一下")))["sources"]],["a","b"])


class VisionEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = Store(root/"history")
        self.media = MediaStore(root/"media")
        self.codex = FakeMedia(root/"unused.png")
        self.gateway = RoutedGateway(lambda *args: decision("收到"))
        self.events = []
        self.engine = ObservedEngine(self.store, self.gateway, lambda e,p: self.events.append((e,p)), media=self.media, codex_media=self.codex)
        self.addCleanup(self.engine.stop_all)
        self.cid = self.store.create("zzz-trio")["id"]
        self.store.update(self.cid,{"settings":{"participants":["gemini"],"maxRounds":1}})

    def send(self, text=None, **kwargs):
        result = self.engine.start(self.cid,text,**kwargs)
        self.assertTrue(self.engine.wait_finished(result))
        return self.store.get(self.cid)["messages"]

    def test_visual_followup_rereads_original_then_shares_new_evidence(self):
        image = self.media.add(png())
        self.send("图片里有什么？",attachments=[image["id"]])
        self.codex.analyzer = lambda *args: "左上角写着 B-17。"
        messages = self.send("再看看这张图左上角写着什么？")
        self.assertEqual(len(self.codex.analysis_calls),2)
        latest = [m for m in messages if m["role"]=="user"][-1]
        self.assertEqual(latest["imageDescription"],"左上角写着 B-17。")
        self.assertEqual(latest["imageAnalysis"]["imageIds"],[image["id"]])
        self.assertIn("所引用图片的 Codex 视觉描述", context(self.gateway.calls[-1][2])[-1]["content"])
        self.send()
        self.assertEqual(len(self.codex.analysis_calls),2)

    def test_deep_report_progress_and_safe_metadata_survive_storage(self):
        calls=[]
        def report(paths,prompt,cancel,*,mode,on_progress):
            calls.append(mode)
            on_progress({"stage":"deep","model":"gpt-6-astra","reasoningEffort":"ultra"})
            self.assertEqual(self.engine.state_snapshot()[self.cid]["imageAnalysis"]["stage"],"deep")
            return {"description":"有两个蓝色方块", "model":"gpt-6-astra", "reasoningEffort":"ultra", "serviceTier":"fast", "elapsedMs":1400,"cached":False,"escalated":False,"privatePath":"secret"}
        self.codex.analyze_report=report
        image=self.media.add(png())
        messages=self.send("深度分析这张图",attachments=[image["id"]])
        self.assertEqual(calls,["deep"])
        metadata=messages[0]["imageAnalysis"]
        self.assertEqual(metadata["model"],"gpt-6-astra")
        self.assertNotIn("secret",json.dumps(metadata))
        final=next(p for e,p in reversed(self.events) if e=="state")
        self.assertEqual(final["imageAnalysis"],{})

    def test_deep_failure_marks_partial_result_without_exposing_exception(self):
        self.codex.analyze_report=lambda *args,**kwargs: {"description":"只能确认一个方块", "model":"gpt-6.1-sol", "warning":"raw credential or upstream body must not be echoed"}
        image=self.media.add(png())
        messages=self.send("看看图里有什么",attachments=[image["id"]])
        self.assertTrue(messages[0]["imageAnalysis"]["partial"])
        self.assertTrue(any(m.get("kind")=="notice" for m in messages))
        self.assertNotIn("raw credential",json.dumps(messages))
        self.assertTrue(self.gateway.calls)
