from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core.runtime.knowledge_providers.local_files import discover_files_at
from backend.services.plan_form import (
    PlanFields,
    PlanFormError,
    decode_plan_upload,
    delete_reference,
    list_references,
    parse_plan,
    render_plan,
    save_plan,
    save_reference,
    save_reference_note,
    template_markdown,
)

LEGACY_PLAN = Path(__file__).resolve().parents[1] / "support" / "legacy_main_plan.md"


class PlanFormParseTests(unittest.TestCase):
    def test_legacy_plan_keeps_subject_unit_stages_and_other_constraints(self) -> None:
        # Hermetic copy of the pre-form plan: harness/knowledge/plan/main_plan.md is
        # rewritten by the GUI, so the test must not depend on its current content.
        text = LEGACY_PLAN.read_text(encoding="utf-8")
        fields = parse_plan(text)
        self.assertIn("PET", fields.subject)
        self.assertIn("1,000", fields.functional_unit)
        self.assertIn("Cradle-to-Point-of-Sale", fields.life_cycle_stages)
        self.assertIn("CML", fields.conditions)
        self.assertIn("ecoinvent", fields.conditions)
        self.assertNotIn("**研究对象**", fields.conditions)
        self.assertNotIn("水瓶案例学习.md", fields.conditions)

    def test_conditions_with_own_headings_survive_round_trip(self) -> None:
        conditions = (
            "## 1. 研究目的与范围定义\n- **研究目的**：比较三个情景。\n"
            "## 2. 生命周期影响评价方法与指标\n- **选用的 LCIA 方法**：`CML v4.8 2016 no LT`。"
        )
        fields = PlanFields("PET 瓶", "1,000 个", "Cradle-to-Gate", conditions)
        again = parse_plan(render_plan(fields, ["水瓶案例学习.md"]))
        self.assertEqual(again.subject, "PET 瓶")
        self.assertIn("CML", again.conditions)
        self.assertIn("## 1. 研究目的与范围定义", again.conditions)
        self.assertNotIn("水瓶案例学习.md", again.conditions)
        self.assertEqual(parse_plan(render_plan(again, [])), again)

    def test_template_and_round_trip(self) -> None:
        template = template_markdown()
        self.assertIn("## section 1", template)
        self.assertIn("用户不能填写，请到界面手动选择。", template)
        self.assertEqual(template.count("## section "), 8)
        self.assertEqual(parse_plan(template), PlanFields("", "", "", ""))
        filled = parse_plan(
            "## section 1\n\n瓶子\n\n"
            "## section 5\n\n不要读数据库\n\n"
            "## section 6\n\n不要读方法\n\n"
            "## section 7\n\n不要读指标\n\n"
            "## section 8\n\n不截断\n"
        )
        self.assertEqual(filled.subject, "瓶子")
        self.assertEqual(filled.conditions, "不截断")
        self.assertNotIn("不要读", filled.conditions)
        fields = PlanFields("瓶子", "1 000 个", "摇篮到大门", "不截断")
        again = parse_plan(render_plan(fields, ["notes.md"]))
        self.assertEqual(again, fields)

    def test_unrecognized_markdown_becomes_conditions(self) -> None:
        fields = parse_plan("# 随便写的计划\n\n只要比较两个情景。\n")
        self.assertEqual(fields.subject, "")
        self.assertIn("只要比较两个情景", fields.conditions)


class PlanReferenceTests(unittest.TestCase):
    def test_save_lists_uploaded_references_and_rejects_unsafe_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = save_reference(root, "资料.md", b"# ref\n")
            self.assertEqual(saved["name"], "资料.md")
            save_plan(root, PlanFields("对象", "1 kg", "生产", ""))
            text = (root / "harness/knowledge/plan/main_plan.md").read_text(encoding="utf-8")
            self.assertIn("harness/knowledge/inputs/资料.md", text)
            self.assertEqual([item["name"] for item in list_references(root)], ["资料.md"])
            delete_reference(root, "资料.md")
            self.assertEqual(list_references(root), [])
            with self.assertRaises(PlanFormError):
                save_reference(root, "../escape.md", b"x")
            saved_binary = save_reference(root, "script.exe", b"x")
            self.assertEqual(saved_binary["name"], "script.exe")
            with self.assertRaises(PlanFormError) as duplicate:
                save_reference(root, "script.exe", b"changed")
            self.assertIn("不能上传同名文件", str(duplicate.exception))
            self.assertEqual((root / "harness/knowledge/inputs/script.exe").read_bytes(), b"x")
            self.assertEqual(save_reference(root, "无扩展名", b"")["size"], 0)
            noted = save_reference_note(root, "script.exe", "  按表格中的距离建模  ")
            self.assertEqual(noted["note"], "按表格中的距离建模")
            listed = {item["name"]: item["note"] for item in list_references(root)}
            self.assertEqual(listed["script.exe"], "按表格中的距离建模")
            notes_path = root / "harness/knowledge/inputs/reference-notes.json"
            self.assertEqual(
                notes_path.read_text(encoding="utf-8"),
                '{\n  "script.exe": "按表格中的距离建模"\n}\n',
            )
            self.assertNotIn("reference-notes.json", listed)
            discovered = {
                item["path"]
                for item in discover_files_at(root, "harness/knowledge/inputs/")["files"]
            }
            self.assertIn("harness/knowledge/inputs/reference-notes.json", discovered)
            notes_path.unlink()
            legacy = root / "harness/knowledge/inputs/.reference-notes.json"
            legacy.write_text('{"script.exe": "旧注释"}\n', encoding="utf-8")
            migrated = {item["name"]: item["note"] for item in list_references(root)}
            self.assertEqual(migrated["script.exe"], "旧注释")
            self.assertFalse(legacy.exists())
            self.assertTrue(notes_path.is_file())
            delete_reference(root, "script.exe")
            self.assertNotIn("script.exe", {item["name"] for item in list_references(root)})
            save_reference(root, "案例/证据.md", b"# nested\n")
            save_reference(root, "其他/证据.md", b"# other\n")
            nested = {item["name"]: item["path"] for item in list_references(root)}
            self.assertEqual(
                nested["案例/证据.md"],
                "harness/knowledge/inputs/案例/证据.md",
            )
            self.assertIn("其他/证据.md", nested)
            noted_nested = save_reference_note(root, "案例/证据.md", "只读运输表")
            self.assertEqual(noted_nested["note"], "只读运输表")
            delete_reference(root, "案例/证据.md")
            self.assertFalse((root / "harness/knowledge/inputs/案例").exists())
            self.assertIn("其他/证据.md", {item["name"] for item in list_references(root)})
            with self.assertRaises(PlanFormError):
                save_reference(root, "../escape.md", b"x")
            with self.assertRaises(PlanFormError):
                save_reference(root, "案例/../escape.md", b"x")
            with self.assertRaises(PlanFormError):
                decode_plan_upload("plan.pdf", b"not markdown")


class PlanApiTests(unittest.TestCase):
    def test_import_save_and_reference_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("backend.api.app.PROJECT_ROOT", root):
                client = TestClient(app)
                imported = client.post(
                    "/api/plan/import",
                    files={"file": ("plan.md", "## 研究对象\n\n瓶子\n".encode(), "text/markdown")},
                )
                self.assertEqual(imported.status_code, 200)
                self.assertEqual(imported.json()["fields"]["subject"], "瓶子")

                uploaded = client.post(
                    "/api/references",
                    files={"files": ("证据.md", b"# evidence\n", "text/markdown")},
                )
                self.assertEqual(uploaded.status_code, 200)
                self.assertEqual(uploaded.json()["files"][0]["name"], "证据.md")

                duplicate = client.post(
                    "/api/references",
                    files=[
                        ("files", ("新资料.md", b"new", "text/plain")),
                        ("files", ("证据.md", b"overwrite", "text/markdown")),
                    ],
                )
                self.assertEqual(duplicate.status_code, 400)
                self.assertIn("不能上传同名文件", duplicate.json()["detail"])
                self.assertEqual((root / "harness/knowledge/inputs/证据.md").read_bytes(), b"# evidence\n")
                self.assertFalse((root / "harness/knowledge/inputs/新资料.md").exists())

                noted = client.put(
                    "/api/references/证据.md/note",
                    json={"note": "用其中的运输距离"},
                )
                self.assertEqual(noted.status_code, 200)
                self.assertEqual(noted.json()["file"]["note"], "用其中的运输距离")

                saved = client.put(
                    "/api/plan",
                    json={
                        "subject": "瓶子",
                        "functional_unit": "1 kg",
                        "life_cycle_stages": "生产",
                        "conditions": "不截断",
                    },
                )
                self.assertEqual(saved.status_code, 410)

                template = client.get("/api/plan/template")
                self.assertEqual(template.status_code, 200)
                self.assertIn("## section 1", template.text)
                self.assertIn("用户不能填写，请到界面手动选择。", template.text)

                removed = client.delete("/api/references/证据.md")
                self.assertEqual(removed.status_code, 200)
                self.assertEqual(removed.json()["files"], [])

                nested = client.post(
                    "/api/references",
                    data={"paths": ["案例/证据.md", "其他/说明.txt"]},
                    files=[
                        ("files", ("证据.md", b"# nested\n", "text/markdown")),
                        ("files", ("说明.txt", b"note", "text/plain")),
                    ],
                )
                self.assertEqual(nested.status_code, 200)
                self.assertEqual(
                    [item["name"] for item in nested.json()["files"]],
                    ["其他/说明.txt", "案例/证据.md"],
                )
                noted = client.put(
                    "/api/references/案例/证据.md/note",
                    json={"note": "文件夹里的表"},
                )
                self.assertEqual(noted.status_code, 200)
                self.assertEqual(noted.json()["file"]["note"], "文件夹里的表")
                escaped = client.post(
                    "/api/references",
                    data={"paths": "../escape.md"},
                    files={"files": ("escape.md", b"x", "text/plain")},
                )
                self.assertEqual(escaped.status_code, 400)
                removed_nested = client.delete("/api/references/案例/证据.md")
                self.assertEqual(removed_nested.status_code, 200)
                self.assertFalse((root / "harness/knowledge/inputs/案例").exists())
                self.assertTrue((root / "harness/knowledge/inputs/其他/说明.txt").is_file())


class PlanFormV2StructuredTests(unittest.TestCase):
    def test_v2_selectable_sections_stay_in_the_note(self) -> None:
        fields = parse_plan(
            "## section 2\n\n数量：1000\n单位：瓶\n在德国交付\n\n"
            "## section 3\n\n原材料获取、制造\n不包括使用\n\n"
            "## section 4\n\n德国\n2024\n\n"
            "## section 7\n\n使用所选方法的全部指标。\n\n"
            "## section 8\n\n- 不截断\n"
        )
        self.assertEqual(fields.functional_unit, "附加说明：数量：1000\n单位：瓶\n在德国交付")
        self.assertEqual(fields.life_cycle_stages, "附加说明：原材料获取、制造\n不包括使用")
        self.assertEqual(fields.conditions, "地域与时间：德国\n2024\n\n- 不截断")
        self.assertNotIn("全部指标", fields.conditions)

    def test_v2_place_text_stays_in_one_box(self) -> None:
        fields = parse_plan("## section 4\n\n地域：德国\n研究年份：无要求\n")
        self.assertEqual(fields.conditions, "地域与时间：地域：德国\n研究年份：无要求")
