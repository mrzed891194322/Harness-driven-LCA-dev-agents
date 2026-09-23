"""Smoke tests for GUI path configuration and interface construction."""

from __future__ import annotations

import unittest

from gui import config
from gui.main import build_ui
from tests.conftest import GUI_ROOT, PROJECT_ROOT


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

    def test_build_ui_includes_settings_agent_assets(self) -> None:
        _demo, _theme, _css, js_code = build_ui()
        self.assertIn("guiSelectSettings_agent", js_code)
        self.assertIn("guiOpenAgentSettings", js_code)
        self.assertIn("guiSelectAgentForm_codex", js_code)
        self.assertIn("guiSelectAgentForm_pi", js_code)
        self.assertIn("#settings-agent-card-codex", _css)
        self.assertIn("#settings-open-agent-btn", _css)
        self.assertIn("#settings-opencode-refresh-btn", _css)
        self.assertIn("#settings-pi-refresh-btn", _css)


class SettingsTabTests(unittest.TestCase):
    def test_init_check_status_update_pending_prefix(self) -> None:
        from gui.ui.components.tab_initial import (
            AGENT_CHOICES,
            PENDING_INIT_STATUS,
            init_check_status_update,
        )

        self.assertEqual(PENDING_INIT_STATUS, "状态：待检查")
        self.assertEqual(AGENT_CHOICES, ["codex", "claude", "opencode", "pi"])
        update = init_check_status_update(None)
        self.assertEqual(update["value"], "状态：待检查")
        self.assertIn("init-check-status-pending", update["elem_classes"])

    def test_init_check_status_update_success_prefix(self) -> None:
        from gui.ui.components.tab_initial import init_check_status_update

        update = init_check_status_update(True, "成功")
        self.assertEqual(update["value"], "状态：成功")
        self.assertIn("init-check-status-ok", update["elem_classes"])

    def test_settings_nav_switches_agent_panel(self) -> None:
        from gui.ui.components.tab_initial import apply_settings_nav

        updates = apply_settings_nav("agent")
        self.assertEqual(len(updates), 2)
        self.assertIn("settings-section-hidden", updates[0]["elem_classes"])
        self.assertNotIn("settings-section-hidden", updates[1]["elem_classes"])

    def test_agent_form_switches_single_backend(self) -> None:
        from gui.ui.components.tab_initial import apply_agent_form

        updates = apply_agent_form("claude")
        self.assertEqual(len(updates), 8)
        self.assertIn("settings-section-hidden", updates[0]["elem_classes"])
        self.assertNotIn("settings-section-hidden", updates[1]["elem_classes"])
        self.assertIn("settings-section-hidden", updates[2]["elem_classes"])
        self.assertIn("settings-section-hidden", updates[3]["elem_classes"])
        self.assertIn("settings-agent-card-active", updates[5]["elem_classes"])

    def test_model_catalog_choices_keep_default_and_current(self) -> None:
        from gui.ui.components.tab_initial import (
            CATALOG_MODEL_WORKERS,
            LOCAL_DEFAULT_MODEL_LABEL,
            model_catalog_choices,
        )

        self.assertEqual(CATALOG_MODEL_WORKERS, ("opencode", "pi"))
        choices = model_catalog_choices(
            ["anthropic/claude-sonnet-4-5", "openai/gpt-4o"],
            "saved/custom",
        )
        self.assertEqual(choices[0], (LOCAL_DEFAULT_MODEL_LABEL, ""))
        values = [value for _label, value in choices]
        self.assertEqual(
            values,
            ["", "anthropic/claude-sonnet-4-5", "openai/gpt-4o", "saved/custom"],
        )

    def test_refresh_model_catalog_updates_dropdown_choices(self) -> None:
        from unittest.mock import patch

        from gui.ui.events.tab_initial import refresh_model_catalog

        with patch(
            "core.agents.catalog.list_models",
            return_value=(
                True,
                "已加载 2 个模型",
                ["anthropic/claude-sonnet-4-5", "openai/gpt-4o"],
            ),
        ):
            update = refresh_model_catalog("opencode", "keep/custom")
        payload = dict(update)
        values = [value for _label, value in payload["choices"]]
        self.assertEqual(payload["value"], "keep/custom")
        self.assertIn("anthropic/claude-sonnet-4-5", values)
        self.assertIn("keep/custom", values)

    def test_refresh_model_catalog_keeps_value_on_failure(self) -> None:
        from unittest.mock import patch

        from gui.ui.events.tab_initial import refresh_model_catalog

        with patch(
            "core.agents.catalog.list_models",
            return_value=(False, "未安装", []),
        ):
            update = refresh_model_catalog("pi", "keep-me")
        payload = dict(update)
        self.assertNotIn("choices", payload)
        self.assertNotIn("value", payload)

    def test_bind_tab_initial_events_does_not_invalidate_on_upload(self) -> None:
        import inspect

        from gui.ui.events.tab_initial import bind_tab_initial_events

        source = inspect.getsource(bind_tab_initial_events)
        self.assertNotIn("ref_upload_file.upload", source)
        self.assertNotIn("ref_upload_file.delete", source)
        self.assertNotIn(
            "ref_upload_file", inspect.signature(bind_tab_initial_events).parameters
        )


class WorkDetailsJsonTests(unittest.TestCase):
    def test_read_work_details_json_missing_invalid_and_valid(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from gui.ui.events.tab_lci import read_work_details_json

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "extracted-bom.json"
            payload, warning = read_work_details_json(path)
            self.assertIsNone(payload)
            self.assertIsNotNone(warning)
            assert warning is not None
            self.assertIn("缺少文件", warning)

            path.write_text("{not json", encoding="utf-8")
            payload, warning = read_work_details_json(path)
            self.assertIsNone(payload)
            self.assertIsNotNone(warning)
            assert warning is not None
            self.assertIn("无法解析 JSON", warning)

            path.write_text('{"items": []}', encoding="utf-8")
            payload, warning = read_work_details_json(path)
            self.assertEqual(payload, {"items": []})
            self.assertIsNone(warning)

    def test_spec_examples_are_readable_work_details_json(self) -> None:
        from gui.ui.events.tab_lci import read_work_details_json

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
        assert isinstance(bom_payload, dict)
        assert isinstance(mapping_payload, dict)
        self.assertIn("items", bom_payload)
        self.assertIn("items", mapping_payload)

    def test_build_ui_js_uses_work_details_tab_title(self) -> None:
        _demo, _theme, _css, js_code = build_ui()
        self.assertIn("工作细节", js_code)
        self.assertNotIn("'LCI清单'", js_code)


if __name__ == "__main__":
    unittest.main()
