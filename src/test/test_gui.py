"""Smoke tests for GUI path configuration and interface construction."""

from __future__ import annotations

import unittest

from support import GUI_ROOT, PROJECT_ROOT  # noqa: E402

from GUI import config  # noqa: E402
from GUI.main import build_ui  # noqa: E402


class GuiConfigurationTests(unittest.TestCase):
    def test_paths_resolve_from_repository_root(self) -> None:
        self.assertEqual(config.PROJECT_ROOT, PROJECT_ROOT)
        self.assertEqual(config.GUI_ROOT, GUI_ROOT)

        expected_paths = (
            config.PLAN_INPUT_TEMPLATE_PATH,
            config.REVISE_TEMPLATE_PATH,
            config.KNOWLEDGE_DIR,
        )
        for path in expected_paths:
            self.assertTrue(path.exists(), path)


class GuiBuildTests(unittest.TestCase):
    def test_build_ui_creates_gradio_blocks(self) -> None:
        demo, _theme, _css, _js_code = build_ui()
        self.assertEqual(type(demo).__name__, "Blocks")
        self.assertGreater(len(demo.blocks), 0)


class SettingsTabTests(unittest.TestCase):
    def test_init_check_status_update_pending_prefix(self) -> None:
        from ui.components.tab_initial import (
            AGENT_CHOICES,
            PENDING_INIT_STATUS,
            init_check_status_update,
        )

        self.assertEqual(PENDING_INIT_STATUS, "状态：待检查")
        self.assertEqual(AGENT_CHOICES, ["codex", "claude", "opencode", "dsh"])
        update = init_check_status_update(None)
        self.assertEqual(update["value"], "状态：待检查")
        self.assertIn("init-check-status-pending", update["elem_classes"])

    def test_init_check_status_update_success_prefix(self) -> None:
        from ui.components.tab_initial import init_check_status_update

        update = init_check_status_update(True, "成功")
        self.assertEqual(update["value"], "状态：成功")
        self.assertIn("init-check-status-ok", update["elem_classes"])


class WorkDetailsJsonTests(unittest.TestCase):
    def test_config_points_at_inventory_json(self) -> None:
        self.assertEqual(
            config.EXTRACTED_BOM_RELATIVE_PATH.as_posix(),
            "workspace/outputs/inventory/extracted-bom.json",
        )
        self.assertEqual(
            config.PROCESS_MAPPING_RELATIVE_PATH.as_posix(),
            "workspace/outputs/inventory/process-mapping.json",
        )

    def test_read_work_details_json_missing_invalid_and_valid(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from ui.events.tab_lci import read_work_details_json

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "extracted-bom.json"
            payload, warning = read_work_details_json(path)
            self.assertIsNone(payload)
            self.assertIsNotNone(warning)
            self.assertIn("缺少文件", warning)

            path.write_text("{not json", encoding="utf-8")
            payload, warning = read_work_details_json(path)
            self.assertIsNone(payload)
            self.assertIsNotNone(warning)
            self.assertIn("无法解析 JSON", warning)

            path.write_text('{"items": []}', encoding="utf-8")
            payload, warning = read_work_details_json(path)
            self.assertEqual(payload, {"items": []})
            self.assertIsNone(warning)

    def test_spec_examples_are_readable_work_details_json(self) -> None:
        from ui.events.tab_lci import read_work_details_json

        bom_example = (
            PROJECT_ROOT
            / "harness"
            / "specs"
            / "02-inventory-extraction"
            / "references"
            / "examples"
            / "extracted-bom.json"
        )
        mapping_example = (
            PROJECT_ROOT
            / "harness"
            / "specs"
            / "03-dataset-mapping"
            / "references"
            / "examples"
            / "process-mapping.json"
        )
        bom_payload, bom_warning = read_work_details_json(bom_example)
        mapping_payload, mapping_warning = read_work_details_json(mapping_example)
        self.assertIsNone(bom_warning)
        self.assertIsNone(mapping_warning)
        self.assertIsInstance(bom_payload, dict)
        self.assertIsInstance(mapping_payload, dict)
        self.assertIn("items", bom_payload)
        self.assertIn("items", mapping_payload)

    def test_build_ui_js_uses_work_details_tab_title(self) -> None:
        _demo, _theme, _css, js_code = build_ui()
        self.assertIn("工作细节", js_code)
        self.assertNotIn("'LCI清单'", js_code)


if __name__ == "__main__":
    unittest.main()
