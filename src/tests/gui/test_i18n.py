"""Tests for GUI locale helpers and .env persistence."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from gui.functions.settings.settings import (
    load_gui_language,
    load_gui_settings,
    save_developer_settings,
)
from gui.i18n import normalize_locale, t


class GuiI18nTests(unittest.TestCase):
    def test_normalize_locale(self) -> None:
        self.assertEqual(normalize_locale("en"), "en")
        self.assertEqual(normalize_locale("English"), "en")
        self.assertEqual(normalize_locale("zh"), "zh")
        self.assertEqual(normalize_locale(None), "zh")

    def test_translate_known_keys(self) -> None:
        self.assertEqual(t("tab.terminal", "zh"), "终端显示")
        self.assertEqual(t("tab.terminal", "en"), "Terminal")

    def test_save_developer_settings_persists_gui_lang(self) -> None:
        with self._temporary_root() as temp_dir:
            root = Path(temp_dir)
            env_path = root / ".env"
            env_path.write_text('GUI_PORT="7860"\n', encoding="utf-8")
            save_developer_settings(gui_port=7860, gui_lang="en", project_root=root)
            text = env_path.read_text(encoding="utf-8")
            self.assertIn('GUI_LANG="en"', text)
            self.assertEqual(load_gui_language(root), "en")
            settings = load_gui_settings(root)
            self.assertEqual(settings["gui_lang"], "en")

    def _temporary_root(self):
        import tempfile

        return tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        os.environ.pop("GUI_LANG", None)


if __name__ == "__main__":
    unittest.main()
