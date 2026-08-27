"""Regression tests for clean_dir targets and presets."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import support  # noqa: F401,E402

from scripts.clean_dir import main as clean_main  # noqa: E402
from scripts.clean_dir.config import CLEAN_PRESETS  # noqa: E402


class CleanDirectoryTests(unittest.TestCase):
    def test_clean_removes_generated_run_data_but_keeps_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            (workspace / "inputs").mkdir(parents=True)
            (workspace / "memory").mkdir()
            (workspace / "outputs").mkdir()
            (workspace / "tmp").mkdir()
            plan_path = workspace / "inputs" / "plan.md"
            plan_path.write_text("plan", encoding="utf-8")
            (workspace / "memory" / "old.json").write_text("{}", encoding="utf-8")
            memory_readme = workspace / "memory" / "README.md"
            memory_readme.write_text("keep", encoding="utf-8")
            (workspace / "outputs" / "old.json").write_text("{}", encoding="utf-8")
            (workspace / "tmp" / "cache.json").write_text("{}", encoding="utf-8")
            tmp_readme = workspace / "tmp" / "README.md"
            tmp_readme.write_text("keep", encoding="utf-8")

            targets = [
                {
                    "name": "workspace",
                    "path": workspace,
                    "gitignore": workspace / ".gitignore",
                    "ignored_dirs": ["memory/**", "outputs/**", "tmp/**"],
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
            self.assertTrue(tmp_readme.exists())
            self.assertFalse((workspace / "memory" / "old.json").exists())
            self.assertFalse((workspace / "outputs" / "old.json").exists())
            self.assertFalse((workspace / "tmp" / "cache.json").exists())

    def test_clean_knowledge_root_files_keeps_tracked_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "harness" / "knowledge"
            knowledge.mkdir(parents=True)
            readme = knowledge / "README.md"
            readme.write_text("keep", encoding="utf-8")
            gitignore = knowledge / ".gitignore"
            gitignore.write_text("*", encoding="utf-8")
            user_file = knowledge / "sample.pdf"
            user_file.write_text("data", encoding="utf-8")

            targets = [
                {
                    "name": "knowledge",
                    "path": knowledge,
                    "gitignore": gitignore,
                    "clean_root_files": True,
                    "keep_patterns": [".gitignore", "README.md"],
                }
            ]
            with (
                patch.object(clean_main, "CLEAN_TARGETS", targets),
                patch.object(clean_main, "PROJECT_ROOT", root),
            ):
                self.assertEqual(
                    clean_main.run_clean(yes=True, target="knowledge"),
                    0,
                )

            self.assertTrue(readme.exists())
            self.assertTrue(gitignore.exists())
            self.assertFalse(user_file.exists())

    def test_preset_whole_lca_runs_targets_in_order(self) -> None:
        calls: list[str] = []

        def fake_single(target_name: str, *, dry_run: bool = False) -> int:
            del dry_run
            calls.append(target_name)
            return 0

        with patch.object(clean_main, "_run_single_target", fake_single):
            self.assertEqual(clean_main.run_clean(yes=True, preset="whole-lca"), 0)

        self.assertEqual(calls, CLEAN_PRESETS["whole-lca"])

    def test_preset_fails_fast_on_first_error(self) -> None:
        calls: list[str] = []

        def fake_single(target_name: str, *, dry_run: bool = False) -> int:
            del dry_run
            calls.append(target_name)
            return 1 if target_name == "knowledge" else 0

        with patch.object(clean_main, "_run_single_target", fake_single):
            self.assertEqual(clean_main.run_clean(yes=True, preset="whole-lca"), 1)

        self.assertEqual(calls, ["knowledge"])

    def test_openlca_target_uses_shared_cleanup(self) -> None:
        with patch.object(
            clean_main,
            "run_openlca_clean",
            return_value=(True, "deleted 2 openLCA entity(ies)", {}),
        ):
            self.assertEqual(clean_main.run_clean(yes=True, target="openlca"), 0)

    def test_target_and_preset_are_mutually_exclusive(self) -> None:
        self.assertEqual(
            clean_main.run_clean(yes=True, target="workspace", preset="whole-lca"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
