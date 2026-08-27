"""Tests for workflow executor helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import support  # noqa: F401,E402

from functions.utils.executor.private_utils import executor_utils  # noqa: E402


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
            executor_utils.clean_dir_command(target="workspace"),
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
            patch("functions.file_sync.main.sync_files", fake_sync),
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
