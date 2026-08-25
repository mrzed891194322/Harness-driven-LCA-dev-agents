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
            executor_utils.CLEAN_WORKSPACE_COMMAND,
        )


if __name__ == "__main__":
    unittest.main()
