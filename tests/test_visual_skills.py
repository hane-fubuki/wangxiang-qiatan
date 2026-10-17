"""Visual-skill loading is bounded, current and independent of local installs."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.visual_skills import (
    MAX_DOCUMENT_BYTES,
    MAX_DOCUMENT_CHARACTERS,
    MAX_REFERENCE_BYTES,
    _safe_file,
    character_visual_reference,
)


class VisualSkillTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / "skills" / "zzz-trio-reference"
        self.references = self.root / "references"
        self.references.mkdir(parents=True)
        self.images = self.root / "assets" / "reference-images"
        self.images.mkdir(parents=True)
        environment = patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        environment.start()
        self.addCleanup(environment.stop)

    def write(self, name, text):
        path = self.references / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_fixed_message_slots_map_to_their_own_character(self):
        self.write("comparison-and-prompts.md", "比较：头顶水平环和后脑竖环不能混同。")
        for slot, stem, marker in (("gemini", "sunna", "千夏当前浅绿发"),
                                  ("deepseek", "nangong-yu", "南宫羽当前黑粉卷梢"),
                                  ("gpt", "aria-human", "爱芮当前人形四束发")):
            self.write(stem + ".md", marker)
            result = character_visual_reference(slot)
            self.assertIn(marker, result["text"])
            self.assertIn("头顶水平环和后脑竖环不能混同", result["text"])
            self.assertIn(str(self.references / (stem + ".md")), result["source"])
            self.assertIn("comparison-and-prompts.md", result["source"])

    def test_rereads_character_and_comparison_after_skill_updates(self):
        self.write("sunna.md", "千夏更新前")
        self.write("comparison-and-prompts.md", "规则更新前")
        first = character_visual_reference("gemini")
        self.write("sunna.md", "千夏更新后")
        self.write("comparison-and-prompts.md", "规则更新后")
        second = character_visual_reference("gemini")
        self.assertIn("千夏更新前", first["text"])
        self.assertIn("千夏更新后", second["text"])
        self.assertIn("规则更新后", second["text"])
        self.assertNotIn("更新前", second["text"])

    def test_missing_skill_uses_distinct_identifiers_and_default_human_aria(self):
        for slot, details in (("gemini", ("浅鼠尾草绿", "右腿", "314")),
                              ("deepseek", ("珊瑚粉卷梢", "左大腿", "近水平")),
                              ("gpt", ("默认人形", "上下四束", "近竖直", "机器人"))):
            with self.subTest(slot=slot):
                result = character_visual_reference(slot)
                self.assertIn("内置", result["source"])
                self.assertNotIn("referencePath", result)
                for detail in details:
                    self.assertIn(detail, result["text"])

    def test_missing_comparison_does_not_discard_valid_character_update(self):
        self.write("aria-human.md", "新版爱芮：四束发，后脑竖环。")
        result = character_visual_reference("gpt")
        self.assertIn("新版爱芮", result["text"])
        self.assertIn("内置三人差异", result["source"])
        self.assertIn("用户明确要求的换装", result["text"])

    def test_bad_character_data_falls_back_without_breaking_generation(self):
        path = self.references / "sunna.md"
        invalid = (b"", b"\xff\xfe", b"null\x00text", b"x" * (MAX_DOCUMENT_BYTES + 1),
                   ("字" * (MAX_DOCUMENT_CHARACTERS + 1)).encode("utf-8"))
        for data in invalid:
            with self.subTest(size=len(data)):
                path.write_bytes(data)
                result = character_visual_reference("gemini")
                self.assertIn("内置", result["source"])
                self.assertIn("浅鼠尾草绿", result["text"])

    def test_oversized_comparison_uses_bounded_fallback(self):
        self.write("sunna.md", "千夏技能正文")
        self.write("comparison-and-prompts.md", "x" * (MAX_DOCUMENT_BYTES + 1))
        result = character_visual_reference("gemini")
        self.assertIn("千夏技能正文", result["text"])
        self.assertIn("内置三人差异", result["source"])
        self.assertLess(len(result["text"]), MAX_DOCUMENT_CHARACTERS)

    def test_does_not_follow_document_links_or_read_personality_files(self):
        self.write("sunna.md", "外观：[链接](../../outside-secret.md)\n## 模型佐证与待补充\n不应载入的模型描述")
        self.write("sunna-personality.md", "不应载入的剧情剧透")
        (self.root.parent / "outside-secret.md").write_text("不应载入的私密内容", encoding="utf-8")
        result = character_visual_reference("gemini")
        self.assertNotIn("不应载入", result["text"])
        self.assertIn("外观", result["text"])

    def test_unknown_slots_never_become_paths(self):
        for slot in ("../sunna", "sunna", "nangong-yu", "../../config", "gpt/../", None, []):
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                character_visual_reference(slot)

    def test_relative_codex_home_fails_closed(self):
        with patch.dict(os.environ, {"CODEX_HOME": "../another-place"}):
            result = character_visual_reference("gemini")
        self.assertIn("内置", result["source"])
        self.assertNotIn("referencePath", result)

    def test_unset_codex_home_uses_home_dot_codex_skill(self):
        default_root = self.home / ".codex" / "skills" / "zzz-trio-reference" / "references"
        default_root.mkdir(parents=True)
        (default_root / "sunna.md").write_text("来自默认安装目录", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True), patch("backend.visual_skills.Path.home", return_value=self.home):
            result = character_visual_reference("gemini")
        self.assertIn("来自默认安装目录", result["text"])

    def test_safe_file_rejects_parent_escape(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        self.assertIsNone(_safe_file(self.root, "../outside.md", MAX_DOCUMENT_BYTES))

    def test_symlink_escape_does_not_import_outside_file(self):
        outside = self.home / "outside.md"
        outside.write_text("私密外部文件", encoding="utf-8")
        try:
            (self.references / "sunna.md").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("This environment does not allow creating symlinks")
        result = character_visual_reference("gemini")
        self.assertNotIn("私密外部文件", result["text"])
        self.assertIn("内置", result["source"])

    def test_only_fixed_nonempty_png_reference_is_returned(self):
        image = self.images / "aria-human-turnaround.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        self.assertEqual(character_visual_reference("gpt")["referencePath"], str(image))
        self.assertNotIn("referencePath", character_visual_reference("gemini"))
        image.write_bytes(b"not a PNG")
        self.assertNotIn("referencePath", character_visual_reference("gpt"))
        with image.open("wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\n")
            handle.truncate(MAX_REFERENCE_BYTES + 1)
        self.assertNotIn("referencePath", character_visual_reference("gpt"))

    def test_reference_image_symlink_outside_skill_is_not_returned(self):
        outside = self.home / "outside.png"
        outside.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        try:
            (self.images / "sunna-turnaround.png").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("This environment does not allow creating symlinks")
        self.assertNotIn("referencePath", character_visual_reference("gemini"))


if __name__ == "__main__":
    unittest.main()
