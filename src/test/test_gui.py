"""Regression tests for the currently supported GUI surface."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
GUI_ROOT = SRC_ROOT / "GUI"

# The GUI keeps script-compatible top-level imports so that
# ``python src/GUI/main.py`` remains a supported entry point.
for import_root in (SRC_ROOT, GUI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from GUI import config  # noqa: E402
from GUI.main import build_ui  # noqa: E402


class GuiConfigurationTests(unittest.TestCase):
    def test_paths_resolve_from_repository_root(self) -> None:
        self.assertEqual(config.PROJECT_ROOT, PROJECT_ROOT)
        self.assertEqual(config.GUI_ROOT, GUI_ROOT)

        expected_paths = (
            config.PLAN_INPUT_TEMPLATE_PATH,
            config.CLEAN_SCRIPT_PATH,
            config.FILE_SYNC_SCRIPT_PATH,
            config.INIT_RAG_SCRIPT_PATH,
            config.OPENLCA_CHECK_DIR,
        )
        for path in expected_paths:
            self.assertTrue(path.exists(), path)

        self.assertEqual(
            config.USER_FILE_DIR,
            PROJECT_ROOT / "workspace" / "inputs" / "references" / "file",
        )
        self.assertEqual(
            config.USER_DATA_DIR,
            PROJECT_ROOT / "workspace" / "inputs" / "references" / "data",
        )
        self.assertEqual(
            config.LCI_MAPPING_FILE_PATH,
            PROJECT_ROOT
            / "workspace"
            / "outputs"
            / "LCI"
            / "human_readable_mapping.md",
        )

    def test_gui_source_has_no_active_legacy_script_paths(self) -> None:
        source_files = GUI_ROOT.rglob("*.py")
        source = "\n".join(path.read_text(encoding="utf-8") for path in source_files)

        self.assertNotIn('"scripts/initialization/main.py"', source)
        self.assertNotIn('"scripts/clean_dir/main.py"', source)
        self.assertNotIn('"workspace" / "plan"', source)
        self.assertNotIn('"workspace" / "LCI"', source)


class GuiBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.demo, *_ = build_ui()

    def _components_with_value(self, text: str):
        return [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "value", None) == text
        ]

    def test_build_ui_creates_gradio_blocks(self) -> None:
        self.assertEqual(type(self.demo).__name__, "Blocks")
        self.assertGreater(len(self.demo.blocks), 0)

    def test_removed_plan_and_lci_actions_are_disabled(self) -> None:
        for elem_id in ("quick-action-plan", "quick-action-lci"):
            matches = [
                component
                for component in self.demo.blocks.values()
                if getattr(component, "elem_id", None) == elem_id
            ]
            self.assertEqual(len(matches), 1, elem_id)
            self.assertFalse(matches[0].interactive, elem_id)

        for label in ("⚡ 执行计划", "⚡ 执行 LCI 制定"):
            matches = self._components_with_value(label)
            self.assertEqual(len(matches), 1, label)
            self.assertFalse(matches[0].interactive, label)

    def test_project_initialization_action_remains_enabled(self) -> None:
        matches = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "quick-action-project"
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].interactive)


if __name__ == "__main__":
    unittest.main()
