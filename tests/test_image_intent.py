"""Image intent stays local, immediate, and scoped to the current chat turn."""
import unittest

from backend.image_intent import image_edit_requested, image_request_context, image_requested
from backend.engine import _image_subjects


def user(content):
    return {"role": "user", "content": content}


def assistant(content, **extra):
    return {"role": "assistant", "content": content, **extra}


class ImageIntentTests(unittest.TestCase):
    def test_renamed_group_keeps_photo_subjects_without_adding_user(self):
        for name in ("妄想天使组合", "妄想茶话会", "三小只"):
            with self.subTest(name=name):
                include_user, subjects = _image_subjects(f"画{name}的合照", "zzz-trio", ["gemini", "deepseek", "gpt"])
                self.assertFalse(include_user)
                self.assertEqual(set(subjects), {"gemini", "deepseek", "gpt"})

    def test_zoom_to_inspect_is_not_a_request_to_generate_an_edited_picture(self):
        self.assertFalse(image_requested("把这张图放大看看左上角的小字",has_images=True))
        self.assertTrue(image_requested("请把这张图放大并发送给我",has_images=True))
        self.assertTrue(image_requested("把这张图放大看看左上角的小字",intent="image",has_images=True))

    def test_direct_photography_and_roleplay_actions(self):
        for text in ("大家一起合影吧", "千夏我们拍张照", "（举起手机）来张自拍", "拍照", "合影",
                     "能不能给我拍张照片", "@南宫羽 我们一起合影吧", "千夏和我拍张合照", "请给我们拍一张合照",
                     "我们来张照片吧", "（拿起手机）自拍", "请拍摄一张照片", "千夏，和我拍张合照吧",
                     "给我拍你们三人的合照", "拍一张千夏和爱芮的合影", "我和千夏、爱芮三人一起合影吧",
                     "千夏，和一只猫拍张合照吧", "千夏和爱芮合影，不要南宫羽", "（举起手机，和大家合影）",
                     "来，我们合个影吧", "咱们合个影吧", "一起合张影吧", "我们合一张影吧",
                     "想和你们拍张合照", "我们来一张你的自拍"):
            with self.subTest(text=text):
                self.assertTrue(image_requested(text))

    def test_drawing_generation_and_quoted_prompt_as_subject(self):
        for text in ("帮我画一只猫", "画一只猫", "生成一张海报", "生成一张日落", "请制作一个猫咪头像",
                     "请根据这个提示词生成一张图片", "画一张教程封面", "请画一只“猫”", "@GPT 帮我绘制一幅水彩",
                     "/画图 蓝色方块", "/生图 一片星空", "你能帮我画一只猫吗", "请生成一张图片，提示词是‘蓝天白云’",
                     "生成一张很漂亮的海报", "画一只可爱的猫"):
            with self.subTest(text=text):
                self.assertTrue(image_requested(text))

    def test_pronoun_photo_requests_are_immediate_commands(self):
        history = [user("千夏换上浅蓝外套，我们在海边。"),
                   assistant("好呀，我就在海边等你！", speakerName="千夏")]
        for text in ("给她拍张照", "给她们拍张照", "请给她拍一张照片", "能不能给她拍张照片", "帮他们拍张合照",
                     "给她和我拍张合照", "请给她们和我拍一张合影", "能不能给她和爱芮拍张合照"):
            with self.subTest(text=text):
                self.assertTrue(image_requested(text, history=history))
                self.assertEqual(image_request_context(text, history), text)
                self.assertFalse(image_edit_requested(text, has_images=True))

    def test_prior_appearance_reference_is_not_a_past_action(self):
        history = [user("千夏换上浅蓝外套，我们在海边。")]
        for text in ("照刚才的样子画", "按刚才的样子画一张", "请照刚才的样子画一张图", "按刚才说的画一张",
                     "按照前面描述的形象绘制一幅插画", "照之前的造型画吧", "按上面的场景拍张照"):
            with self.subTest(text=text):
                self.assertTrue(image_requested(text, history=history))
                self.assertEqual(image_request_context(text, history), text)
                self.assertFalse(image_edit_requested(text, has_images=True))

    def test_referential_creation_keeps_past_tutorial_and_negation_exclusions(self):
        for text in ("刚才给她拍了张照", "给她拍过照", "昨天给她们拍张照", "下次给她拍张照", "如果有空，给她拍张照",
                     "怎么给她拍张照", "教我给她拍张照", "给她拍张照需要多久？", "给她拍张照是什么意思？",
                     "不用给她拍张照", "照刚才的样子画过了", "按刚才的样子画了一张", "明天照刚才的样子画",
                     "怎样照刚才的样子画", "照刚才的样子画需要多久", "你觉得照刚才的样子画怎么样？",
                     "照刚才的样子画，先别生成", "请不要按刚才的样子画一张", "‘照刚才的样子画’", "`给她拍张照`",
                     "刚才给她和我拍了张合照", "不要给她和我拍张合照", "怎么给她和我拍张合照", "明天给她和我拍张合照"):
            with self.subTest(text=text):
                self.assertFalse(image_requested(text, has_images=True))

    def test_tutorial_translation_estimates_and_examples_are_not_requests(self):
        for text in ("生成一张海报需要多久？", "画一只猫是什么意思？", "画一只猫，这句话翻译成英文",
                     "生成一张图片，先别画，我只是举个例子", "怎么生成一张图片", "如何画一只猫", "教我画一只猫",
                     "拍照的步骤是什么？", "生成图片的原理是什么", "能不能生成头像？", "你会画画吗？",
                     "请解释画一只猫这句话的含义", "画一只猫，译成英文", "我想讨论生成图片的方法"):
            with self.subTest(text=text):
                self.assertFalse(image_requested(text))

    def test_negation_cancellation_and_edit_discussion_override_action_words(self):
        for text in ("别画了", "不要画一只猫", "请不要生成一张海报", "不用拍照", "取消这次生图",
                     "生成一张图片，暂时别画", "生成一张头像，先不生成", "把这张图片改成白色，不用生图，只说说思路",
                     "帮我画一只猫，但我只想说说思路", "算了，合影改天吧"):
            with self.subTest(text=text):
                self.assertFalse(image_requested(text, has_images=True))

    def test_past_future_conditionals_and_appreciation_do_not_generate(self):
        for text in ("昨天我们拍了张合影", "我刚才画了一只猫", "上次生成的图片很漂亮", "我们之前合影过",
                     "明天一起合影吧", "如果有空我们拍照", "等你准备好再合影", "下次帮我画一只猫",
                     "我打算画一只猫", "这张自拍很好看", "照片颜色真漂亮", "画风真可爱", "这张图片画得不错",
                     "我想画一只猫", "大家喜欢拍照吗？", "合影真好看", "自拍很漂亮", "拍照很开心",
                     "画一只猫真好玩", "拍照是我的爱好", "拍照好玩吗？", "如果有空，画一只猫", "明天，拍照吧",
                     "画图是我的爱好", "画出来的效果不错"):
            with self.subTest(text=text):
                self.assertFalse(image_requested(text))

    def test_quotes_code_and_stage_directions_are_not_commands(self):
        for text in ("“画一只猫”", '"生成一张图片"', "「大家一起合影吧」", "他说：‘画一只猫’",
                     "`画一只猫`", "```text\n生成一张图片\n```", "> 大家一起合影吧", "（举起手机拍了张照片）"):
            with self.subTest(text=text):
                self.assertFalse(image_requested(text))
        self.assertTrue(image_requested("请生成一张图片，参考这段：```text\n一只猫\n```"))

    def test_visual_edit_requires_visual_object_for_implicit_references(self):
        for text in ("把蓝圈改成绿色", "把背景改成白色", "把头发换成蓝色", "去掉水印", "背景改成蓝色"):
            with self.subTest(text=text):
                self.assertTrue(image_requested(text, has_images=True))
                self.assertFalse(image_requested(text, has_images=False))
        for text in ("把这张图片改成白色", "修改这张照片的背景", "把海报上的名字改成小夏", "重绘上一张图"):
            self.assertTrue(image_requested(text, has_images=True), text)
        for text in ("把名字改成小夏", "把旧记录移除", "把这句话改成英文", "把南宫羽的说话语气改成温柔一点",
                     "修改模型设置", "把技能改成幽默一点", "移除聊天记录", "把文件改成白色"):
            self.assertFalse(image_requested(text, has_images=True), text)

    def test_explicit_mode_preserves_previous_override_contract(self):
        self.assertTrue(image_requested("蓝色方块", intent="image"))
        self.assertTrue(image_requested("如何画猫", intent="image"))
        self.assertFalse(image_requested("画一只猫", intent="unknown"))
        for value in (None, [], {}, 1, "", "  "):
            self.assertFalse(image_requested(value))

    def test_edit_kind_tracks_the_first_action_and_requires_a_visual_target(self):
        for text in ("背景改成蓝色", "把蓝圈改成绿色", "你好，背景改成蓝色", "千夏，把这张图片背景改成白色",
                     "重绘上一张图片", "合影真好看，背景改成蓝色"):
            self.assertTrue(image_edit_requested(text, has_images=True), text)
        self.assertTrue(image_edit_requested("把这张图片改成白色"))
        self.assertFalse(image_edit_requested("背景改成蓝色"))
        for text in ("大家合影，背景改成蓝色", "大家合个影吧，背景改成蓝色", "大家合影背景改成蓝色",
                     "生成一张海报，背景改成蓝色", "画一只猫，把背景改成蓝色", "/画图 蓝圈，背景改成蓝色",
                     "把名字改成小夏", "把旧记录移除", "把背景改成白色，不用生图，只说说思路",
                     "明天，背景改成蓝色", "如何把这张图片改成白色？", "好的", "合个影真好看"):
            self.assertFalse(image_edit_requested(text, has_images=True), text)

    def test_natural_group_photo_variants_are_shared_by_invitations(self):
        for proposal in ("我们合个影吧？", "一起合张影吧", "咱们合一张影吧", "来，我们合个影吧"):
            history = [user("休息一下吧"), assistant(proposal, speakerName="千夏")]
            self.assertTrue(image_requested("好，来一张", history=history), proposal)
            self.assertEqual(image_request_context("好，来一张", history), f"千夏的提议：{proposal}\n用户当前要求：好，来一张")
        for text in ("我们合个影真好看", "明天合个影吧", "不要合个影", "合个影是什么意思？"):
            self.assertFalse(image_requested(text), text)

    def test_recent_invitation_acceptance_includes_speaker_identity(self):
        history = [user("今天玩什么？"), assistant("不如我和你合影吧！", speakerName="千夏", provider="gemini")]
        for confirmation in ("好呀，来一张", "就按你说的拍", "好呀", "好的", "行", "来一张", "好呀来一张", "那就这样拍"):
            with self.subTest(confirmation=confirmation):
                self.assertTrue(image_requested(confirmation, history=history))
                text = image_request_context(confirmation, history)
                self.assertEqual(text, "千夏的提议：不如我和你合影吧！\n用户当前要求：" + confirmation)
        self.assertFalse(image_requested("好的，继续聊天", history=history))
        self.assertFalse(image_requested("好呀，先别拍", history=history))

    def test_drawing_invitation_and_provider_fallback(self):
        history = [user("猫很可爱"), assistant("我可以给你画一只猫，要不要？", provider="gpt")]
        self.assertTrue(image_requested("好呀", history=history))
        self.assertTrue(image_request_context("好呀", history).startswith("gpt的提议："))
        for text in ("好呀", "来一张", "就按你说的拍"):
            self.assertFalse(image_requested(text), text)

    def test_only_latest_user_turn_can_supply_an_invitation(self):
        old = [user("做什么？"), assistant("我们一起合影吧", speakerName="千夏")]
        for later in ([user("聊聊音乐"), assistant("最近在练习新歌")], [user("换个话题吧")]):
            history = old + later
            self.assertFalse(image_requested("好呀", history=history))
            self.assertEqual(image_request_context("好呀", history), "好呀")
        self.assertFalse(image_requested("好呀", history=[user("做什么？"), assistant("要不要一起喝茶？")]))

    def test_generated_image_blocks_generic_confirmation_even_if_prior_offer_remains(self):
        invitation = [user("来聊聊"), assistant("我们一起合影吧", speakerName="千夏")]
        for image in (assistant("图片已生成", kind="image"), assistant("给你图片", attachments=[{"id": "a" * 32}])):
            history = invitation + [image]
            for text in ("好的", "好呀", "来一张", "继续聊天"):
                with self.subTest(kind=image, text=text):
                    self.assertFalse(image_requested(text, history=history))
                    self.assertEqual(image_request_context(text, history), text)
            self.assertTrue(image_requested("再生成一张海报", history=history))

    def test_current_user_message_may_already_be_in_history(self):
        history = [user("做什么？"), assistant("我们一起拍张合影吧", speakerName="爱芮"), user("好呀")]
        self.assertTrue(image_requested("好呀", history=history))
        self.assertIn("爱芮的提议", image_request_context("好呀", history))

    def test_group_context_uses_recent_offer_but_not_a_superseded_invitation(self):
        history = [user("休息一下"), assistant("我们一起合影吧", speakerName="千夏"), assistant("我准备好了！", speakerName="南宫羽")]
        self.assertTrue(image_requested("好呀", history=history))
        self.assertIn("千夏的提议", image_request_context("好呀", history))
        history.append(assistant("不如我们去喝茶吧", speakerName="爱芮"))
        self.assertFalse(image_requested("好呀", history=history))
        cancelled = history[:2] + [assistant("算了，先别拍了", speakerName="千夏")]
        self.assertFalse(image_requested("好呀", history=cancelled))

    def test_system_quoted_negative_and_stale_offers_do_not_trigger(self):
        for proposal in ("明天我们一起合影吧", "不要拍照了，我们休息吧", "“我们一起合影吧”", "昨天一起合影很好看"):
            self.assertFalse(image_requested("好呀", history=[user("聊什么？"), assistant(proposal)]), proposal)
        self.assertFalse(image_requested("好呀", history=[{"role": "system", "content": "我们一起合影吧"}]))
        long_turn = [user("聊什么？"), assistant("我们一起合影吧")] + [assistant("准备好了")] * 12
        self.assertFalse(image_requested("好呀", history=long_turn))

    def test_direct_request_does_not_import_other_scene_or_character(self):
        history = [user("聊什么？"), assistant("我和千夏在海边拍照吧", speakerName="爱芮")]
        request = "帮我画南宫羽在图书馆看书"
        self.assertTrue(image_requested(request, history=history))
        self.assertEqual(image_request_context(request, history), request)
        self.assertEqual(image_request_context(None, history), "")


if __name__ == "__main__":
    unittest.main()
