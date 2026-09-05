"""Regression tests for readiness status checks."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from support import PROJECT_ROOT  # noqa: F401,E402

from GUI.functions.settings.check_status import (  # noqa: E402
    check_openlca_result,
    run_initialization_checks,
)
from scripts.check_status import main as check_status_main  # noqa: E402


class CheckStatusTests(unittest.TestCase):
    def test_openlca_check_uses_package_import_without_main_collision(self) -> None:
        with patch(
            "scripts.check_status.openlca_check.get_openlca_health",
            return_value={"ok": True, "attempt_count": 1},
        ):
            self.assertEqual(check_openlca_result(), (True, "可用"))

    def test_execution_gate_requires_all_checks(self) -> None:
        with (
            patch(
                "GUI.functions.settings.check_status.check_agent_result",
                return_value=(True, "可用"),
            ),
            patch(
                "GUI.functions.settings.check_status.check_openlca_result",
                return_value=(False, "不可用"),
            ),
        ):
            ok, failed = run_initialization_checks()
        self.assertFalse(ok)
        self.assertEqual(failed, ["OpenLCA"])

    def test_check_status_fails_when_agent_check_fails(self) -> None:
        with (
            patch.object(
                check_status_main,
                "check_project_environment",
                return_value=(False, "opencode未安装"),
            ),
            patch.object(sys, "argv", ["check_status", "--only", "agents"]),
        ):
            with self.assertRaisesRegex(RuntimeError, "opencode未安装"):
                check_status_main.main()

    def test_check_status_passes_agent_argument(self) -> None:
        captured: dict[str, object] = {}

        def fake_check(*, project_root=None, agent=None):
            captured["agent"] = agent
            captured["project_root"] = project_root
            return True, "可用"

        with (
            patch.object(
                check_status_main,
                "check_project_environment",
                side_effect=fake_check,
            ),
            patch.object(
                sys,
                "argv",
                ["check_status", "--only", "agents", "--agent", "claude"],
            ),
        ):
            check_status_main.main()
        self.assertEqual(captured["agent"], "claude")


if __name__ == "__main__":
    unittest.main()
