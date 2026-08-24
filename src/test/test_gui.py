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
            config.CLEAN_SCRIPT_PATH,
            config.FILE_SYNC_SCRIPT_PATH,
            config.INIT_RAG_SCRIPT_PATH,
        )
        for path in expected_paths:
            self.assertTrue(path.exists(), path)


class GuiBuildTests(unittest.TestCase):
    def test_build_ui_creates_gradio_blocks(self) -> None:
        demo, _theme, _css, _js_code = build_ui()
        self.assertEqual(type(demo).__name__, "Blocks")
        self.assertGreater(len(demo.blocks), 0)


class SettingsNavTests(unittest.TestCase):
    def test_settings_section_visibility_covers_nav_keys(self) -> None:
        from ui.components.tab_initial import (
            DEFAULT_SETTINGS_NAV,
            SETTINGS_NAV_ITEMS,
            SETTINGS_SECTION_VISIBILITY,
            SETTINGS_SECTION_HIDDEN_CLASS,
            apply_settings_nav,
            apply_settings_nav_ui,
            settings_section_classes,
        )

        self.assertEqual(len(SETTINGS_SECTION_VISIBILITY[DEFAULT_SETTINGS_NAV]), 4)
        self.assertEqual(
            set(SETTINGS_SECTION_VISIBILITY),
            {key for key, _label in SETTINGS_NAV_ITEMS},
        )
        updates = apply_settings_nav("init_check")
        self.assertEqual(len(updates), 4)
        unknown = apply_settings_nav("missing")
        self.assertEqual(len(unknown), 4)
        self.assertEqual(len(apply_settings_nav_ui("agent")), 8)
        self.assertEqual(settings_section_classes(True), ["settings-section"])
        self.assertEqual(
            settings_section_classes(False),
            ["settings-section", SETTINGS_SECTION_HIDDEN_CLASS],
        )


if __name__ == "__main__":
    unittest.main()
