"""Regression tests for the plan editor helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import PROJECT_ROOT  # noqa: E402

from GUI import config  # noqa: E402
from GUI.functions import plan_editor  # noqa: E402


class PlanEditorTests(unittest.TestCase):
    VALID_PLAN = """---
template_kind: lca_plan_input
template_version: 1
---

# 测试计划

## 1. 范围
- **研究对象**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  测试对象

  ---
"""

    FORM_TEMPLATE = """---
template_kind: lca_plan_input
template_version: 1
---

# 测试计划

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
            self.assertEqual(
                plan_editor.load_plan_text(current, default),
                self.VALID_PLAN,
            )
            template, values = plan_editor.load_plan_form(current, default)
            self.assertEqual(template.source, self.VALID_PLAN)
            self.assertEqual(values, ["测试对象"])

    def test_dev_prompt_plan_is_importable_and_round_trips_exactly(self) -> None:
        plan_path = PROJECT_ROOT / "docs" / "dev" / "prompts" / "plan.md"
        source = plan_path.read_text(encoding="utf-8")
        template = plan_editor.parse_execution_plan_template(plan_path)

        self.assertEqual(len(template.fields), 13)
        self.assertEqual(source.count("<!-- PLAN_TEXTBOX -->"), 13)
        self.assertNotIn("<!-- PLAN_INPUT", source)
        self.assertIn("德国销售点 PET 水瓶", template.values[0])
        self.assertEqual(
            plan_editor.serialize_execution_plan(template, template.values),
            source,
        )

    def test_preview_hides_yaml_front_matter(self) -> None:
        preview = plan_editor.render_plan_preview(self.VALID_PLAN)
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
            self.assertEqual(loaded, self.VALID_PLAN)
            self.assertEqual(current.read_text(encoding="utf-8"), "original")

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
        plain_plan = """---
template_kind: lca_plan_input
template_version: 1
---

# 只读执行计划

## 范围
这里的内容由模板直接提供。
"""
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
            self.assertIn("***✍️ 用户填写内容区***", saved)
            self.assertEqual(
                plan_editor.extract_plan_values(template, saved),
                ["标题", "对象", "补充\n第二行", "CML"],
            )

    def test_invalid_plan_does_not_replace_existing_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "plan.md"
            target.write_text("original", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "template_kind"):
                plan_editor.save_execution_plan("# invalid", target)
            self.assertEqual(target.read_text(encoding="utf-8"), "original")

    def test_template_fields_are_dynamic_and_metadata_is_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            template_path = Path(temp) / "execution_plan.md"
            template_path.write_text(self.FORM_TEMPLATE, encoding="utf-8")
            template = plan_editor.parse_execution_plan_template(template_path)
            self.assertEqual(
                [field.field_id for field in template.fields],
                ["textbox_01", "textbox_02", "textbox_03", "textbox_04"],
            )
            self.assertEqual(template.fields[2].rows, 4)

            extended_path = Path(temp) / "extended.md"
            extended_path.write_text(
                self.FORM_TEMPLATE.replace(
                    "\n## 2. 方法",
                    "\n- **新增字段**：\n"
                    "  <!-- PLAN_TEXTBOX -->\n"
                    "  ---\n"
                    "  ***✍️ 用户填写内容区***\n\n"
                    "  ---\n\n"
                    "## 2. 方法",
                ),
                encoding="utf-8",
            )
            extended = plan_editor.parse_execution_plan_template(extended_path)
            self.assertEqual(len(extended.fields), 5)
            self.assertEqual(extended.fields[3].field_id, "textbox_04")

            malformed = Path(temp) / "malformed.md"
            malformed.write_text(
                self.FORM_TEMPLATE.replace(
                    "***✍️ 用户填写内容区***",
                    "***填写区***",
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "未连接完整"):
                plan_editor.parse_execution_plan_template(malformed)

    def test_default_marked_regions_parse_and_preserve_template_structure(self) -> None:
        template = plan_editor.parse_execution_plan_template(
            config.PLAN_INPUT_TEMPLATE_PATH
        )
        self.assertEqual(len(template.fields), 13)
        self.assertEqual(
            [field.field_id for field in template.fields[:2]],
            ["textbox_01", "textbox_02"],
        )
        self.assertEqual(len(plan_editor.render_plan_segments(template)), 14)

        serialized = plan_editor.serialize_execution_plan(
            template,
            [f"填写值 {index}" for index in range(len(template.fields))],
        )

        self.assertIn("template_kind: lca_plan_input", serialized)
        self.assertIn("## 模块 1：项目背景与评估目标", serialized)
        self.assertEqual(serialized.count("<!-- PLAN_TEXTBOX -->"), 13)
        self.assertIn("***✍️ 用户填写内容区***", serialized)
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
        plan = (
            "---\n"
            "template_kind: lca_plan_input\n"
            "template_version: 1\n"
            "---\n\n"
            f"# 超限模板\n\n{blocks}\n"
        )

        with self.assertRaisesRegex(ValueError, "超过上限 20"):
            plan_editor.parse_execution_plan_text(plan)

    def test_plan_input_is_optional_for_plain_markdown_templates(self) -> None:
        plain_template = """---
template_kind: lca_plan_input
template_version: 1
---

# 纯 Markdown 计划

## 范围

### 研究对象

普通说明文字。
"""
        with tempfile.TemporaryDirectory() as temp:
            template_path = Path(temp) / "plain.md"
            template_path.write_text(plain_template, encoding="utf-8")

            template = plan_editor.parse_execution_plan_template(template_path)
            rendered = plan_editor.render_template_parts(template)

            self.assertEqual(template.fields, ())
            self.assertTrue(all(isinstance(part, plan_editor.PlanMarkdownPart) for part in rendered))
            self.assertIn("纯 Markdown 计划", rendered[0].content)
            self.assertIn("研究对象", rendered[0].content)

    def test_plan_values_match_by_position_and_pad_missing_fields(self) -> None:
        source_plan = """---
template_kind: lca_plan_input
template_version: 1
---

## 2. 方法
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
        with tempfile.TemporaryDirectory() as temp:
            template_path = Path(temp) / "execution_plan.md"
            template_path.write_text(self.FORM_TEMPLATE, encoding="utf-8")
            template = plan_editor.parse_execution_plan_template(template_path)

            values = plan_editor.extract_plan_values(template, source_plan)

            self.assertEqual(values, ["CML", "PET 水瓶", "", ""])

    def test_existing_plan_round_trip_preserves_unknown_chapter_content(self) -> None:
        source_plan = """---
template_kind: lca_plan_input
template_version: 1
---

# 已有计划

## 1. 范围
- **计划标题**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  已有计划

  ---

## 2. 方法
- **研究对象**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  PET 水瓶

  ---
- **补充内容**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  必须保留
  第二行补充说明

  ---
- **方法**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  CML

  ---
"""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = plan_editor.parse_execution_plan_text(source_plan)
            values = list(staged.values)
            self.assertEqual(values[0], "已有计划")
            self.assertEqual(values[1], "PET 水瓶")
            self.assertIn("必须保留", values[2])

            serialized = plan_editor.serialize_execution_plan(staged, values)
            self.assertIn("PLAN_TEXTBOX", serialized)
            self.assertIn("template_kind: lca_plan_input", serialized)
            self.assertIn("## 1. 范围", serialized)
            self.assertIn("## 2. 方法", serialized)
            self.assertEqual(
                plan_editor.parse_execution_plan_text(serialized).values,
                tuple(values),
            )

    def test_invalid_template_and_upload_do_not_replace_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            template_path = root / "broken.md"
            template_path.write_text(
                self.FORM_TEMPLATE.replace(
                    "***✍️ 用户填写内容区***",
                    "***填写区***",
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "未连接完整"):
                plan_editor.parse_execution_plan_template(template_path)

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

            for metadata_line, expected in (
                ("template_kind: another_kind", "lca_plan_input"),
                ("template_version: 2", "template_version: 1"),
            ):
                invalid = self.FORM_TEMPLATE
                if metadata_line.startswith("template_kind"):
                    invalid = invalid.replace(
                        "template_kind: lca_plan_input",
                        metadata_line,
                    )
                else:
                    invalid = invalid.replace(
                        "template_version: 1",
                        metadata_line,
                    )
                with self.assertRaisesRegex(ValueError, expected):
                    plan_editor.parse_execution_plan_text(invalid)

            valid_path = root / "valid-template.md"
            valid_path.write_text(self.FORM_TEMPLATE, encoding="utf-8")
            values = plan_editor.import_plan_values(
                plan_editor.parse_execution_plan_template(valid_path),
                """---
template_kind: lca_plan_input
template_version: 1
---

# 没有 PLAN_INPUT 的计划
""",
            )
            self.assertEqual(values, ["", "", "", ""])


if __name__ == "__main__":
    unittest.main()
