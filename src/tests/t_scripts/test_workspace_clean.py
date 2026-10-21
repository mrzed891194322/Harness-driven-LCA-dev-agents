"""Regression tests for clean_dir targets, presets, and workflow executor helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.services.workspace_clean as clean_main
from backend.services.workspace_clean import CLEAN_PRESETS


class CleanDirectoryTests(unittest.TestCase):
    def test_clean_removes_generated_run_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "runs" / "_run").mkdir(parents=True)
            (workspace / "artifacts").mkdir()
            (workspace / "tmp").mkdir()
            (workspace / "runs" / "01-intake-gate" / "reviewer-1").mkdir(parents=True)
            (workspace / "runs" / "01-intake-gate" / "reviewer-1" / "old.json").write_text(
                "{}", encoding="utf-8"
            )
            memory_readme = workspace / "runs" / "README.md"
            memory_readme.write_text("keep", encoding="utf-8")
            (workspace / "artifacts" / "old.json").write_text("{}", encoding="utf-8")
            (workspace / "tmp" / "cache.json").write_text("{}", encoding="utf-8")
            tmp_readme = workspace / "tmp" / "README.md"
            tmp_readme.write_text("keep", encoding="utf-8")

            targets = [
                {
                    "name": "workspace",
                    "path": workspace,
                    "gitignore": workspace / ".gitignore",
                    "ignored_dirs": ["runs/**", "artifacts/**", "tmp/**"],
                    "keep_patterns": ["**/README.md", "runs/_run/orchestrator.lock"],
                }
            ]
            with (
                patch.object(clean_main, "CLEAN_TARGETS", targets),
                patch.object(clean_main, "PROJECT_ROOT", root),
            ):
                self.assertEqual(clean_main.run_clean(yes=True), 0)

            self.assertTrue(memory_readme.exists())
            self.assertTrue(tmp_readme.exists())
            self.assertFalse(
                (workspace / "runs" / "01-intake-gate" / "reviewer-1" / "old.json").exists()
            )
            self.assertFalse((workspace / "artifacts" / "old.json").exists())
            self.assertFalse((workspace / "tmp" / "cache.json").exists())

    def test_clean_knowledge_staging_subdirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "harness" / "knowledge"
            inputs = knowledge / "inputs"
            inputs.mkdir(parents=True)
            readme = knowledge / "README.md"
            readme.write_text("keep", encoding="utf-8")
            gitignore = knowledge / ".gitignore"
            gitignore.write_text("*", encoding="utf-8")
            user_file = inputs / "sample.pdf"
            user_file.write_text("data", encoding="utf-8")

            targets = [
                {
                    "name": "knowledge",
                    "path": knowledge,
                    "gitignore": gitignore,
                    "staging_subdirs": ["inputs", "plan"],
                    "keep_patterns": ["README.md"],
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

    def test_clean_knowledge_removes_nested_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "harness" / "knowledge"
            inputs = knowledge / "inputs"
            nested = inputs / "水瓶案例学习"
            nested.mkdir(parents=True)
            readme = knowledge / "README.md"
            readme.write_text("keep", encoding="utf-8")
            gitignore = knowledge / ".gitignore"
            gitignore.write_text("*", encoding="utf-8")
            nested_file = nested / "水瓶案例学习.md"
            nested_file.write_text("case", encoding="utf-8")
            root_copy = inputs / "水瓶案例学习.md"
            root_copy.write_text("case", encoding="utf-8")

            targets = [
                {
                    "name": "knowledge",
                    "path": knowledge,
                    "gitignore": gitignore,
                    "staging_subdirs": ["inputs", "plan"],
                    "keep_patterns": ["README.md"],
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
            self.assertFalse(nested.exists())
            self.assertFalse(root_copy.exists())

    def test_clean_knowledge_plan_subdir(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "harness" / "knowledge"
            plan = knowledge / "plan"
            plan.mkdir(parents=True)
            (knowledge / "README.md").write_text("keep", encoding="utf-8")
            main_plan = plan / "main_plan.md"
            main_plan.write_text("plan", encoding="utf-8")
            (plan / "README.md").write_text("keep", encoding="utf-8")

            targets = [
                {
                    "name": "knowledge",
                    "path": knowledge,
                    "staging_subdirs": ["inputs", "plan"],
                    "keep_patterns": ["README.md"],
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

            self.assertFalse(main_plan.exists())
            self.assertTrue((plan / "README.md").exists())

    def test_preset_whole_lca_targets(self) -> None:
        self.assertEqual(
            CLEAN_PRESETS["whole-lca"],
            ["openlca", "workspace"],
        )
        self.assertEqual(CLEAN_PRESETS["revise-lca"], ["openlca"])
        for targets in CLEAN_PRESETS.values():
            self.assertNotIn("knowledge", targets)

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
            return 1 if target_name == "openlca" else 0

        with patch.object(clean_main, "_run_single_target", fake_single):
            self.assertEqual(clean_main.run_clean(yes=True, preset="whole-lca"), 1)

        self.assertEqual(calls, ["openlca"])

    def test_whole_lca_openlca_sees_workspace_before_it_is_cleaned(self) -> None:
        """Regression (p5-cleanup-lock): UUID cleanup reads workspace LCI/journal."""
        seen: dict[str, bool] = {}
        state = {"workspace_cleaned": False}

        def fake_openlca(dry_run: bool = False):
            seen["workspace_intact"] = not state["workspace_cleaned"]
            return True, "deleted 35 openLCA entity(ies)", {}

        def fake_fs(target_cfg, *, dry_run: bool = False):
            if target_cfg["name"] == "workspace":
                state["workspace_cleaned"] = True
            return 0, 0, 0, 0

        with (
            patch.object(clean_main, "run_openlca_clean", fake_openlca),
            patch.object(clean_main, "_clean_filesystem_target", fake_fs),
        ):
            self.assertEqual(
                clean_main.run_clean(yes=True, preset="whole-lca", clean_staging=False),
                0,
            )
        self.assertTrue(seen["workspace_intact"])
        self.assertTrue(state["workspace_cleaned"])

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

    def test_clean_staging_false_skips_knowledge_staging(self) -> None:
        calls: list[str] = []

        def fake_single(target_name: str, *, dry_run: bool = False) -> int:
            del dry_run
            calls.append(target_name)
            return 0

        with patch.object(clean_main, "_run_single_target", fake_single):
            self.assertEqual(
                clean_main.run_clean(
                    yes=True,
                    preset="whole-lca",
                    clean_staging=False,
                ),
                0,
            )

        self.assertEqual(calls, ["openlca", "workspace"])

    def test_clean_staging_false_with_only_staging_is_noop(self) -> None:
        calls: list[str] = []

        def fake_single(target_name: str, *, dry_run: bool = False) -> int:
            del dry_run
            calls.append(target_name)
            return 0

        with patch.object(clean_main, "_run_single_target", fake_single):
            self.assertEqual(
                clean_main.run_clean(
                    yes=True,
                    target="knowledge",
                    clean_staging=False,
                ),
                0,
            )

        self.assertEqual(calls, [])

    def test_symlink_clean_roots_do_not_follow_external(self) -> None:
        for dir_name in ("runs", "artifacts", "tmp"):
            with self.subTest(dir_name=dir_name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                external = root / "external"
                external.mkdir()
                sentinel = external / "sentinel.txt"
                sentinel.write_text("keep-me", encoding="utf-8")

                workspace = root / "workspace"
                workspace.mkdir()
                link = workspace / dir_name
                link.symlink_to(external, target_is_directory=True)
                (workspace / "inputs").mkdir()

                targets = [
                    {
                        "name": "workspace",
                        "path": workspace,
                        "gitignore": workspace / ".gitignore",
                        "ignored_dirs": ["runs/**", "artifacts/**", "tmp/**"],
                        "keep_patterns": ["**/README.md", "runs/_run/orchestrator.lock"],
                    }
                ]
                with (
                    patch.object(clean_main, "CLEAN_TARGETS", targets),
                    patch.object(clean_main, "PROJECT_ROOT", root),
                ):
                    self.assertEqual(clean_main.run_clean(yes=True), 0)

                self.assertTrue(sentinel.exists())
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep-me")
                self.assertFalse(link.exists() or link.is_symlink())

    def test_clean_keeps_orchestrator_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            run_meta = workspace / "runs" / "_run"
            run_meta.mkdir(parents=True)
            (workspace / "artifacts").mkdir()
            (workspace / "tmp").mkdir()
            lock_path = run_meta / "orchestrator.lock"
            lock_path.write_text("owned", encoding="utf-8")
            attempt = workspace / "runs" / "01-intake-gate" / "reviewer-1"
            attempt.mkdir(parents=True)
            (attempt / "old.json").write_text("{}", encoding="utf-8")

            targets = [
                {
                    "name": "workspace",
                    "path": workspace,
                    "gitignore": workspace / ".gitignore",
                    "ignored_dirs": ["runs/**", "artifacts/**", "tmp/**"],
                    "keep_patterns": ["**/README.md", "runs/_run/orchestrator.lock"],
                }
            ]
            with (
                patch.object(clean_main, "CLEAN_TARGETS", targets),
                patch.object(clean_main, "PROJECT_ROOT", root),
            ):
                self.assertEqual(clean_main.run_clean(yes=True), 0)

            self.assertTrue(lock_path.exists())
            self.assertEqual(lock_path.read_text(encoding="utf-8"), "owned")
            self.assertFalse((attempt / "old.json").exists())

    def test_run_clean_fails_when_workspace_lock_held(self) -> None:
        from backend.services.workspace_clean import workspace_lock

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            memory = workspace / "runs" / "_run"
            memory.mkdir(parents=True)
            (workspace / "artifacts").mkdir()
            (workspace / "tmp").mkdir()
            victim = memory / "victim.json"
            victim.write_text("{}", encoding="utf-8")

            targets = [
                {
                    "name": "workspace",
                    "path": workspace,
                    "gitignore": workspace / ".gitignore",
                    "ignored_dirs": ["runs/**", "artifacts/**", "tmp/**"],
                    "keep_patterns": ["**/README.md", "runs/_run/orchestrator.lock"],
                }
            ]

            with workspace_lock(workspace):
                with (
                    patch.object(clean_main, "CLEAN_TARGETS", targets),
                    patch.object(clean_main, "PROJECT_ROOT", root),
                ):
                    code = clean_main.run_clean(yes=True)

            self.assertEqual(code, 1)
            self.assertTrue(victim.exists())
            self.assertTrue(memory.exists())
            self.assertTrue((workspace / "artifacts").exists())
            self.assertTrue((workspace / "tmp").exists())
            self.assertTrue((memory / "orchestrator.lock").exists())


if __name__ == "__main__":
    unittest.main()
