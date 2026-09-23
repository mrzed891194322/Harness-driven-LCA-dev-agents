"""Regression tests for clean_dir targets, presets, and workflow executor helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import services.workspace as clean_main
from gui.functions.utils.executor.private_utils import executor_utils
from services.workspace import CLEAN_PRESETS


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

    def test_clean_knowledge_removes_nested_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "harness" / "knowledge"
            nested = knowledge / "水瓶案例学习"
            nested.mkdir(parents=True)
            readme = knowledge / "README.md"
            readme.write_text("keep", encoding="utf-8")
            gitignore = knowledge / ".gitignore"
            gitignore.write_text("*", encoding="utf-8")
            nested_file = nested / "水瓶案例学习.md"
            nested_file.write_text("case", encoding="utf-8")
            root_copy = knowledge / "水瓶案例学习.md"
            root_copy.write_text("case", encoding="utf-8")

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
            self.assertFalse(nested.exists())
            self.assertFalse(root_copy.exists())

    def test_clean_inputs_root_files_keeps_readme(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / "workspace" / "inputs"
            inputs.mkdir(parents=True)
            readme = inputs / "README.md"
            readme.write_text("keep", encoding="utf-8")
            plan_path = inputs / "plan.md"
            plan_path.write_text("plan", encoding="utf-8")
            revise_path = inputs / "revise.md"
            revise_path.write_text("revise", encoding="utf-8")

            targets = [
                {
                    "name": "inputs",
                    "path": inputs,
                    "clean_root_files": True,
                    "keep_patterns": ["README.md"],
                }
            ]
            with (
                patch.object(clean_main, "CLEAN_TARGETS", targets),
                patch.object(clean_main, "PROJECT_ROOT", root),
            ):
                self.assertEqual(
                    clean_main.run_clean(yes=True, target="inputs"),
                    0,
                )

            self.assertTrue(readme.exists())
            self.assertFalse(plan_path.exists())
            self.assertFalse(revise_path.exists())

    def test_preset_whole_lca_includes_inputs(self) -> None:
        self.assertEqual(
            CLEAN_PRESETS["whole-lca"],
            ["knowledge", "inputs", "workspace", "openlca"],
        )
        self.assertEqual(CLEAN_PRESETS["revise-lca"], ["knowledge", "openlca"])

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

    def test_clean_staging_false_skips_knowledge_and_inputs(self) -> None:
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

        self.assertEqual(calls, ["workspace", "openlca"])

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


class RunCleanWorkspaceConsoleTests(unittest.TestCase):
    def test_run_clean_workspace_reports_failure_on_nonzero_exit(self) -> None:
        def fake_stream(command_args):
            del command_args
            yield "[System] Process finished with exit code 1.\n"

        with patch.object(executor_utils, "execute_command_stream", fake_stream):
            outputs = list(executor_utils.run_clean_workspace_console())

        self.assertGreaterEqual(len(outputs), 2)
        console, status = outputs[-1]
        self.assertEqual(status, "Failed")
        self.assertIn("exit code 1", console)

    def test_run_clean_workspace_uses_clean_dir_command(self) -> None:
        captured: list[list[str]] = []

        def fake_stream(command_args):
            captured.append(command_args)
            yield "[System] Process finished with exit code 0.\n"

        with patch.object(executor_utils, "execute_command_stream", fake_stream):
            list(executor_utils.run_clean_workspace_console())

        self.assertEqual(
            captured[0],
            executor_utils.clean_dir_command(target="workspace", clean_staging=True),
        )

    def test_clean_dir_command_adds_no_staging_when_disabled(self) -> None:
        command = executor_utils.clean_dir_command(
            preset="whole-lca",
            clean_staging=False,
        )
        self.assertIn("--preset", command)
        self.assertIn("whole-lca", command)
        self.assertIn("--no-staging", command)

    def test_run_clean_preset_console_passes_no_staging(self) -> None:
        captured: list[list[str]] = []

        def fake_stream(command_args):
            captured.append(command_args)
            yield "[System] Process finished with exit code 0.\n"

        with patch.object(executor_utils, "execute_command_stream", fake_stream):
            list(
                executor_utils.run_clean_preset_console(
                    "whole-lca",
                    clean_staging=False,
                )
            )

        self.assertEqual(
            captured[0],
            executor_utils.clean_dir_command(
                preset="whole-lca",
                clean_staging=False,
            ),
        )


class RunPreWorkflowConsoleTests(unittest.TestCase):
    def test_pre_workflow_whole_lca_uses_preset_then_sync(self) -> None:
        preset_calls: list[str] = []

        def fake_preset(preset: str):
            preset_calls.append(preset)
            yield "[System] clean ok\n", "Finished"

        sync_calls: list[str] = []

        class FakeResult:
            def __init__(self, target: str):
                self.target = target
                self.ok = True
                self.message = "ok"
                self.details = []

        def fake_sync(target, **kwargs):
            del kwargs
            sync_calls.append(target)
            return FakeResult(target)

        with (
            patch.object(executor_utils, "run_clean_preset_console", fake_preset),
            patch("gui.functions.file_sync.main.sync_files", fake_sync),
        ):
            outputs = list(
                executor_utils.run_pre_workflow_console(
                    "whole-lca",
                    document_values=[],
                    source_text="# plan\n",
                    ref_upload_file=None,
                )
            )

        self.assertEqual(preset_calls, ["whole-lca"])
        self.assertEqual(sync_calls, ["knowledge", "plan"])
        self.assertEqual(outputs[-1][1], "Finished")

    def test_pre_workflow_whole_lca_clean_command_includes_staging(self) -> None:
        captured: list[list[str]] = []
        sync_calls: list[str] = []

        def fake_stream(command_args):
            captured.append(list(command_args))
            yield "[System] Process finished with exit code 0.\n"

        class FakeResult:
            def __init__(self, target: str):
                self.target = target
                self.ok = True
                self.message = "ok"
                self.details = []

        def fake_sync(target, **kwargs):
            del kwargs
            sync_calls.append(target)
            return FakeResult(target)

        with (
            patch.object(executor_utils, "execute_command_stream", fake_stream),
            patch("gui.functions.file_sync.main.sync_files", fake_sync),
        ):
            outputs = list(
                executor_utils.run_pre_workflow_console(
                    "whole-lca",
                    document_values=[],
                    source_text="# plan\n",
                    ref_upload_file=None,
                )
            )

        self.assertEqual(len(captured), 1)
        command = captured[0]
        self.assertEqual(
            command,
            executor_utils.clean_dir_command(preset="whole-lca", clean_staging=True),
        )
        self.assertIn("--preset", command)
        self.assertIn("whole-lca", command)
        self.assertNotIn("--no-staging", command)
        self.assertEqual(sync_calls, ["knowledge", "plan"])
        self.assertEqual(outputs[-1][1], "Finished")

    def test_pre_workflow_stops_when_clean_fails(self) -> None:
        def fake_preset(preset: str):
            del preset
            yield "[System] fail\n", "Failed"

        workflow_called = False

        def fake_workflow(task: str):
            nonlocal workflow_called
            workflow_called = True
            del task
            yield "", "Finished"

        with (
            patch.object(executor_utils, "run_clean_preset_console", fake_preset),
            patch.object(executor_utils, "run_workflow_command_console", fake_workflow),
        ):
            outputs = list(
                executor_utils.run_pre_workflow_console(
                    "whole-lca",
                    document_values=[],
                    source_text="# plan\n",
                    ref_upload_file=None,
                )
            )

        self.assertFalse(workflow_called)
        self.assertEqual(outputs[-1][1], "Failed")


if __name__ == "__main__":
    unittest.main()
