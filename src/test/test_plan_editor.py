"""Regression tests for the structured Markdown form helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import PROJECT_ROOT  # noqa: E402

from GUI import config  # noqa: E402
from GUI.functions import plan_editor  # noqa: E402


class PlanEditorTests(unittest.TestCase):
    VALID_PLAN = """# 测试计划

## 1. 范围
- **研究对象**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  测试对象

  ---
"""

    FORM_TEMPLATE = """# 测试计划

## 1. 范围
- **计划标题**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  ---
- **研究对象**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  ---
- **补充内容**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  ---

## 2. 方法
- **方法**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  ---
"""

    def test_default_templates_have_no_metadata_and_expected_regions(self) -> None:
        expectations = (
            (config.PLAN_INPUT_TEMPLATE_PATH, "# LCA 执行计划", 9),
            (config.REVISE_TEMPLATE_PATH, "# LCA评估修改", 1),
        )
        for path, heading, count in expectations:
            source = path.read_text(encoding="utf-8")
            parsed = plan_editor.parse_execution_plan_template(path)

            self.assertFalse(source.startswith("---\n"), path)
            self.assertNotIn("template_kind", source)
            self.assertNotIn("template_version", source)
            self.assertIn(heading, source)
            self.assertEqual(source.count("<!-- PLAN_TEXTBOX -->"), count)
            self.assertEqual(len(parsed.fields), count)
            self.assertEqual(
                plan_editor.serialize_execution_plan(parsed, parsed.values),
                source,
            )

    def test_loads_default_template_and_ignores_existing_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current = root / "inputs" / "plan.md"
            default = root / "template.md"
            default.write_text(self.VALID_PLAN, encoding="utf-8")

            self.assertEqual(
                plan_editor.load_plan_text(current, default),
                self.VALID_PLAN,
            )

            current.parent.mkdir()
            current.write_text("# existing", encoding="utf-8")
            template, values = plan_editor.load_plan_form(current, default)
            self.assertEqual(template.source, self.VALID_PLAN)
            self.assertEqual(values, ["测试对象"])

    def test_documents_with_no_or_arbitrary_metadata_round_trip(self) -> None:
        prompt_plan = (
            PROJECT_ROOT / "src" / "GUI" / "ui" / "assets" / "template" / "plan.md"
        ).read_text(encoding="utf-8")
        documents = (
            self.VALID_PLAN,
            (
                "---\n"
                "template_kind: anything\n"
                "template_version: 999\n"
                "custom_key: preserved\n"
                "---\n\n"
                f"{self.VALID_PLAN}"
            ),
            "# 纯 Markdown\n\n没有输入区域。\n",
            prompt_plan,
        )
        for source in documents:
            template = plan_editor.parse_execution_plan_text(source)
            serialized = plan_editor.serialize_execution_plan(
                template,
                template.values,
            )
            self.assertEqual(serialized, source)

        arbitrary = plan_editor.parse_execution_plan_text(documents[1])
        self.assertEqual(arbitrary.metadata["template_kind"], "anything")
        self.assertTrue(arbitrary.front_matter.startswith("---\n"))

    def test_preview_hides_optional_yaml_front_matter(self) -> None:
        source = (
            "---\ntemplate_kind: arbitrary\ncustom: value\n---\n\n"
            f"{self.VALID_PLAN}"
        )
        preview = plan_editor.render_plan_preview(source)
        self.assertNotIn("template_kind", preview)
        self.assertTrue(preview.startswith("# 测试计划"))

    def test_upload_is_staged_without_overwriting_current_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current = root / "plan.md"
            current.write_text("original", encoding="utf-8")
            upload = root / "upload.md"
            upload.write_text(self.VALID_PLAN, encoding="utf-8")

            loaded = plan_editor.read_uploaded_plan(upload)
            improvement = plan_editor.read_uploaded_markdown(
                upload,
                document_label="改进方案",
            )
            self.assertEqual(loaded, self.VALID_PLAN)
            self.assertEqual(improvement, self.VALID_PLAN)
            self.assertEqual(current.read_text(encoding="utf-8"), "original")

            wrong_type = root / "upload.txt"
            wrong_type.write_text(self.VALID_PLAN, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "仅支持上传"):
                plan_editor.read_uploaded_markdown(
                    wrong_type,
                    document_label="改进方案",
                )

    def test_save_validates_then_atomically_replaces_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "inputs" / "plan.md"
            saved_path = plan_editor.save_execution_plan(
                self.VALID_PLAN,
                target,
            )
            self.assertEqual(saved_path, target)
            self.assertEqual(target.read_text(encoding="utf-8"), self.VALID_PLAN)
            self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_plain_markdown_plan_can_be_saved_without_input_markers(self) -> None:
        plain_plan = "# 只读执行计划\n\n## 范围\n这里的内容由模板直接提供。\n"
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "inputs" / "plan.md"
            plan_editor.save_execution_plan(plain_plan, target)
            self.assertEqual(target.read_text(encoding="utf-8"), plain_plan)

    def test_structured_save_writes_marked_plan_directly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            template_path = root / "execution_plan.md"
            target = root / "inputs" / "plan.md"
            template_path.write_text(self.FORM_TEMPLATE, encoding="utf-8")
            template = plan_editor.parse_execution_plan_template(template_path)

            plan_editor.save_structured_plan(
                template,
                ["标题", "对象", "补充\n第二行", "CML"],
                target,
            )

            saved = target.read_text(encoding="utf-8")
            self.assertIn("PLAN_TEXTBOX", saved)
            self.assertNotIn("template_kind", saved)
            self.assertEqual(
                plan_editor.extract_plan_values(template, saved),
                ["标题", "对象", "补充\n第二行", "CML"],
            )

    def test_invalid_plan_does_not_replace_existing_plan(self) -> None:
        malformed = self.VALID_PLAN.replace("***✍️ 用户填写内容区***", "***填写区***")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "plan.md"
            target.write_text("original", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "未连接完整"):
                plan_editor.save_execution_plan(malformed, target)
            self.assertEqual(target.read_text(encoding="utf-8"), "original")

    def test_template_fields_are_dynamic(self) -> None:
        template = plan_editor.parse_execution_plan_text(self.FORM_TEMPLATE)
        self.assertEqual(
            [field.field_id for field in template.fields],
            ["textbox_01", "textbox_02", "textbox_03", "textbox_04"],
        )
        extended = plan_editor.parse_execution_plan_text(
            self.FORM_TEMPLATE.replace(
                "\n## 2. 方法",
                "\n- **新增字段**：\n"
                "  <!-- PLAN_TEXTBOX -->\n"
                "  ---\n"
                "  ***✍️ 用户填写内容区***\n\n"
                "  ---\n\n"
                "## 2. 方法",
            )
        )
        self.assertEqual(len(extended.fields), 5)

    def test_default_marked_regions_render_and_preserve_structure(self) -> None:
        template = plan_editor.parse_execution_plan_template(
            config.PLAN_INPUT_TEMPLATE_PATH
        )
        self.assertEqual(len(plan_editor.render_plan_segments(template)), 10)

        serialized = plan_editor.serialize_execution_plan(
            template,
            [f"填写值 {index}" for index in range(len(template.fields))],
        )

        self.assertFalse(serialized.startswith("---\n"))
        self.assertIn("## 1. 研究对象", serialized)
        self.assertIn("## 8. 资料重点", serialized)
        self.assertIn("## 9. 特殊需求", serialized)
        self.assertEqual(serialized.count("<!-- PLAN_TEXTBOX -->"), 9)
        self.assertEqual(
            plan_editor.parse_execution_plan_text(serialized).values[:2],
            ("填写值 0", "填写值 1"),
        )

    def test_more_than_twenty_editable_regions_is_rejected(self) -> None:
        blocks = "\n".join(
            (
                f"- **字段 {index}**：\n"
                "  <!-- PLAN_TEXTBOX -->\n"
                "  ---\n"
                "  ***✍️ 用户填写内容区***\n\n"
                "  ---"
            )
            for index in range(1, plan_editor.MAX_PLAN_INPUTS + 2)
        )
        with self.assertRaisesRegex(ValueError, "超过上限 20"):
            plan_editor.parse_execution_plan_text(f"# 超限模板\n\n{blocks}\n")

    def test_plain_markdown_has_no_fields(self) -> None:
        template = plan_editor.parse_execution_plan_text(
            "# 纯 Markdown 计划\n\n## 范围\n\n普通说明文字。\n"
        )
        rendered = plan_editor.render_template_parts(template)
        self.assertEqual(template.fields, ())
        self.assertTrue(
            all(
                isinstance(part, plan_editor.PlanMarkdownPart)
                for part in rendered
            )
        )
        self.assertEqual(
            plan_editor.render_document_status(template, "上传计划"),
            "",
        )

    def test_document_navigation_levels_and_anchor_prefix_are_configurable(
        self,
    ) -> None:
        document = plan_editor.parse_markdown_document_text(
            "# 一级\n\n## 二级\n\n### 三级\n"
        )
        segments = plan_editor.render_document_segments(
            document,
            anchor_prefix="shared-document-heading",
            heading_levels=(1, 2, 3),
        )
        toc = plan_editor.render_document_toc(
            document,
            anchor_prefix="shared-document-heading",
            heading_levels=(1, 2, 3),
            title="文档目录",
        )

        rendered = "".join(segments)
        for index, title in enumerate(("一级", "二级", "三级"), start=1):
            self.assertIn(
                f'id="shared-document-heading-{index}"',
                rendered,
            )
            self.assertIn(
                f"[{title}](#shared-document-heading-{index})",
                toc,
            )

    def test_values_match_by_position_and_pad_missing_fields(self) -> None:
        source_plan = """## 2. 方法
- **方法**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  CML

  ---
- **研究对象**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  PET 水瓶

  ---
"""
        template = plan_editor.parse_execution_plan_text(self.FORM_TEMPLATE)
        self.assertEqual(
            plan_editor.extract_plan_values(template, source_plan),
            ["CML", "PET 水瓶", "", ""],
        )

    def test_malformed_markers_and_old_plan_input_are_rejected(self) -> None:
        malformed = self.FORM_TEMPLATE.replace(
            "***✍️ 用户填写内容区***",
            "***填写区***",
            1,
        )
        with self.assertRaisesRegex(ValueError, "未连接完整"):
            plan_editor.parse_execution_plan_text(malformed)

        missing_close = self.FORM_TEMPLATE.replace(
            "\n  ---\n- **研究对象**",
            "\n- **研究对象**",
            1,
        )
        with self.assertRaisesRegex(ValueError, "缺少闭合分隔线"):
            plan_editor.parse_execution_plan_text(missing_close)

        old_plan_input = self.FORM_TEMPLATE.replace(
            "<!-- PLAN_TEXTBOX -->",
            '<!-- PLAN_INPUT id="old" -->',
            1,
        )
        with self.assertRaisesRegex(ValueError, "不再支持 `PLAN_INPUT`"):
            plan_editor.parse_execution_plan_text(old_plan_input)


if __name__ == "__main__":
    unittest.main()
