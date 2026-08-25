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
        self.assertEqual(AGENT_CHOICES, ["codex", "claude", "opencode"])
        update = init_check_status_update(None)
        self.assertEqual(update["value"], "状态：待检查")
        self.assertIn("init-check-status-pending", update["elem_classes"])

    def test_init_check_status_update_success_prefix(self) -> None:
        from ui.components.tab_initial import init_check_status_update

        update = init_check_status_update(True, "成功")
        self.assertEqual(update["value"], "状态：成功")
        self.assertIn("init-check-status-ok", update["elem_classes"])


if __name__ == "__main__":
    unittest.main()
