"""Regression tests for workspace/harness clean_dir targets."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import support  # noqa: F401,E402

from scripts.clean_dir import main as clean_main  # noqa: E402


class CleanDirectoryTests(unittest.TestCase):
    def test_clean_removes_generated_run_data_but_keeps_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            (workspace / "inputs").mkdir(parents=True)
            (workspace / "memory").mkdir()
            (workspace / "outputs").mkdir()
            plan_path = workspace / "inputs" / "plan.md"
            plan_path.write_text("plan", encoding="utf-8")
            (workspace / "memory" / "old.json").write_text("{}", encoding="utf-8")
            memory_readme = workspace / "memory" / "README.md"
            memory_readme.write_text("keep", encoding="utf-8")
            (workspace / "outputs" / "old.json").write_text("{}", encoding="utf-8")

            targets = [
                {
                    "name": "workspace",
                    "path": workspace,
                    "gitignore": workspace / ".gitignore",
                    "ignored_dirs": ["memory/**", "outputs/**"],
                    "keep_patterns": ["**/README.md"],
                }
            ]
            with (
                patch.object(clean_main, "CLEAN_TARGETS", targets),
                patch.object(clean_main, "PROJECT_ROOT", root),
            ):
                self.assertEqual(clean_main.run_clean(yes=True), 0)

            self.assertTrue(plan_path.exists())
            self.assertTrue(memory_readme.exists())
            self.assertFalse((workspace / "memory" / "old.json").exists())
            self.assertFalse((workspace / "outputs" / "old.json").exists())

    def test_workspace_without_inputs_keeps_inputs_and_clears_other_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            (workspace / "inputs" / "references").mkdir(parents=True)
            (workspace / "memory").mkdir()
            (workspace / "outputs").mkdir()
            (workspace / "tmp").mkdir()
            plan_path = workspace / "inputs" / "plan.md"
            plan_path.write_text("plan", encoding="utf-8")
            ref_path = workspace / "inputs" / "references" / "note.txt"
            ref_path.write_text("ref", encoding="utf-8")
            (workspace / "memory" / "old.json").write_text("{}", encoding="utf-8")
            memory_readme = workspace / "memory" / "README.md"
            memory_readme.write_text("keep", encoding="utf-8")
            (workspace / "outputs" / "old.json").write_text("{}", encoding="utf-8")
            (workspace / "tmp" / "cache.json").write_text("{}", encoding="utf-8")
            tmp_readme = workspace / "tmp" / "README.md"
            tmp_readme.write_text("keep", encoding="utf-8")

            targets = [
                {
                    "name": "workspace_without_inputs",
                    "path": workspace,
                    "gitignore": workspace / ".gitignore",
                    "exclude_top_level": ["inputs"],
                    "keep_patterns": ["**/README.md"],
                }
            ]
            with (
                patch.object(clean_main, "CLEAN_TARGETS", targets),
                patch.object(clean_main, "PROJECT_ROOT", root),
            ):
                self.assertEqual(
                    clean_main.run_clean(yes=True, target="workspace_without_inputs"),
                    0,
                )

            self.assertTrue(plan_path.exists())
            self.assertTrue(ref_path.exists())
            self.assertTrue(memory_readme.exists())
            self.assertTrue(tmp_readme.exists())
            self.assertFalse((workspace / "memory" / "old.json").exists())
            self.assertFalse((workspace / "outputs" / "old.json").exists())
            self.assertFalse((workspace / "tmp" / "cache.json").exists())


if __name__ == "__main__":
    unittest.main()
