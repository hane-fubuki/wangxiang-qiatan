"""Check crop fidelity, source mapping and bounded work without model calls."""
from io import BytesIO
import json
import threading
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from backend.codex_provider import CodexCancelled, CodexError
from backend.vision_crops import DETAIL_EDGE, crop_context, current_question, detail_crops


def image_bytes(size=(4000, 2400), format="PNG", **kwargs):
    with Image.new("RGB", size, "white") as image, BytesIO() as target:
        draw = ImageDraw.Draw(image)
        draw.rectangle((size[0] - 70, size[1] - 70, size[0] - 1, size[1] - 1), fill=(5, 90, 160))
        image.save(target, format=format, **kwargs)
        return target.getvalue()


def question(text, history=""):
    return "参考数据\n<visual_question_data>" + json.dumps({"question": text, "history": history}, ensure_ascii=False) + "</visual_question_data>"


class VisionCropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.large = image_bytes()

    def setUp(self):
        self.cancel = threading.Event()

    def test_focus_uses_current_question_not_history_and_preserves_exact_pixels(self):
        crops, info = detail_crops([(self.large, ".png")], question("读出右下角的小字", "之前看左上角"), self.cancel)
        self.assertEqual(len(crops), 1)
        self.assertEqual(info, [{"attachmentIndex": 2, "sourceImage": 1, "sourceSize": [4000, 2400],
                                 "box": [1952, 352, 4000, 2400]}])
        with Image.open(BytesIO(self.large)) as original, Image.open(BytesIO(crops[0][0])) as crop:
            self.assertEqual(crop.size, (2048, 2048))
            self.assertEqual(crop.tobytes(), original.crop(info[0]["box"]).tobytes())
        prompt = crop_context(info, 1)
        self.assertIn("无损裁切", prompt)
        self.assertIn('"sourceImage": 1', prompt)
        self.assertIn("未覆盖区域", prompt)

    def test_large_overview_is_supplemented_by_four_overlapping_native_tiles(self):
        crops, info = detail_crops([(self.large, ".png")], question("检查图中的细节"), self.cancel)
        self.assertEqual(len(crops), 4)
        self.assertEqual({tuple(item["box"]) for item in info},
                         {(0, 0, 2048, 2048), (1952, 0, 4000, 2048),
                          (0, 352, 2048, 2400), (1952, 352, 4000, 2400)})
        for (data, extension), item in zip(crops, info):
            self.assertEqual(extension, ".png")
            with Image.open(BytesIO(data)) as crop:
                self.assertLessEqual(max(crop.size), DETAIL_EDGE)
            self.assertEqual(item["sourceImage"], 1)

    def test_small_images_are_not_cropped_or_upscaled(self):
        small = image_bytes((2048, 1300))
        self.assertEqual(detail_crops([(small, ".png")], "放大右下角", self.cancel), ([], []))
        self.assertEqual(crop_context([], 1), "")

    def test_multiple_large_images_share_four_total_crops(self):
        crops, info = detail_crops([(self.large, ".png")] * 4, "比较全部图片", self.cancel)
        self.assertEqual(len(crops), 4)
        self.assertEqual([item["sourceImage"] for item in info], [1, 2, 3, 4])
        self.assertEqual([item["attachmentIndex"] for item in info], [5, 6, 7, 8])
        self.assertNotIn("path", json.dumps(info))

    def test_explicit_image_number_limits_supplements_to_that_source(self):
        crops, info = detail_crops([(self.large, ".png")] * 3, question("第2张图右下角是什么", "第1张左上"), self.cancel)
        self.assertEqual(len(crops), 1)
        self.assertEqual(info[0]["sourceImage"], 2)
        self.assertEqual(info[0]["attachmentIndex"], 4)

    def test_engine_selected_image_is_not_filtered_again_by_original_ordinal(self):
        for text in ("第2张图右下角是什么", "第二张图右下角是什么"):
            with self.subTest(text=text):
                prompt = "<visual_question_data>" + json.dumps(
                    {"question": text, "imagesAlreadySelected": True,
                     "history": "第一张图的左上角"}, ensure_ascii=False) + "</visual_question_data>"
                crops, info = detail_crops([(self.large, ".png")], prompt, self.cancel)
                self.assertEqual(len(crops), 1)
                self.assertEqual(info[0]["sourceImage"], 1)
                self.assertEqual(info[0]["box"], [1952, 352, 4000, 2400])

    def test_plain_chinese_ordinals_still_filter_original_inputs(self):
        for numeral, expected in (("一", 1), ("二", 2), ("三", 3), ("四", 4)):
            with self.subTest(numeral=numeral):
                crops, info = detail_crops([(self.large, ".png")] * 4,
                                          f"第{numeral}张图右下角的小字", self.cancel)
                self.assertEqual(len(crops), 1)
                self.assertEqual(info[0]["sourceImage"], expected)

    def test_selection_marker_requires_boolean_true(self):
        for marker in (False, "true", 1):
            with self.subTest(marker=marker):
                prompt = json.dumps({"question": "第2张图右下角", "imagesAlreadySelected": marker})
                crops, info = detail_crops([(self.large, ".png")] * 2, prompt, self.cancel)
                self.assertEqual(len(crops), 1)
                self.assertEqual(info[0]["sourceImage"], 2)

    def test_top_side_and_center_regions_keep_coordinates_bounded(self):
        for text, expected in (("顶部细节", 2), ("左侧文字", 2), ("upper-right label", 1), ("中央图形", 1)):
            with self.subTest(text=text):
                crops, info = detail_crops([(self.large, ".png")], text, self.cancel)
                self.assertEqual(len(crops), expected)
                for item in info:
                    left, top, right, bottom = item["box"]
                    self.assertGreaterEqual(left, 0)
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(right, 4000)
                    self.assertLessEqual(bottom, 2400)
                    self.assertLessEqual(max(right - left, bottom - top), DETAIL_EDGE)

    def test_very_large_image_does_not_expand_past_four_crops(self):
        large = image_bytes((8000, 2600))
        crops, info = detail_crops([(large, ".png")], "读取所有细字", self.cancel)
        self.assertEqual(len(crops), 4)
        self.assertTrue(all(max(box["box"][2] - box["box"][0], box["box"][3] - box["box"][1]) <= DETAIL_EDGE for box in info))

    def test_jpeg_orientation_is_applied_before_mapping_coordinates(self):
        exif = Image.Exif()
        exif[274] = 6  # rotate 90 degrees clockwise
        data = image_bytes((2600, 1000), format="JPEG", exif=exif)
        crops, info = detail_crops([(data, ".jpg")], "右下角", self.cancel)
        self.assertEqual(info[0]["sourceSize"], [1000, 2600])
        self.assertEqual(info[0]["box"], [0, 552, 1000, 2600])
        with Image.open(BytesIO(crops[0][0])) as crop:
            self.assertEqual(crop.size, (1000, 2048))

    def test_invalid_data_and_cancellation_do_not_produce_crops(self):
        with self.assertRaises(CodexError):
            detail_crops([(b"not an image", ".png")], "描述", self.cancel)
        self.cancel.set()
        with self.assertRaises(CodexCancelled):
            detail_crops([(self.large, ".png")], "描述", self.cancel)
        self.cancel.clear()
        save = Image.Image.save

        def cancelled_save(image, *args, **kwargs):
            result = save(image, *args, **kwargs)
            self.cancel.set()
            return result

        with patch.object(Image.Image, "save", cancelled_save), self.assertRaises(CodexCancelled):
            detail_crops([(self.large, ".png")], "描述", self.cancel)

    def test_question_parser_ignores_malformed_structured_context(self):
        self.assertEqual(current_question(question("当前右侧", "历史左侧")), "当前右侧")
        self.assertEqual(current_question('{"question":"右下","history":"左上"}'), "右下")
        self.assertEqual(current_question('{"history":"左上"}'), "")
        self.assertEqual(current_question('<visual_question_data>{invalid 左上}</visual_question_data>'), "")


if __name__ == "__main__":
    unittest.main()
