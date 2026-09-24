"""Strict Host Action request/result wire-protocol tests."""

from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.runtime.context import RunContext
from core.runtime.host_action import (
    HostActionResult,
    build_host_request,
    normalize_host_action_result,
    run_host_action,
)
from core.workflow.config.models import HostActionSpec
from harness.tools.shared.context import parse_host_request


def _ctx(**overrides: object) -> dict:
    payload = {
        "run_id": "run-1",
        "stage": "s1",
        "assignment": "s1.executor",
        "attempt": 1,
        "role": "executor",
        "workspace": "/tmp/ws",
        "project_root": "/tmp/proj",
        "metadata": {},
        "handoff_path": "memory/handoffs/x.json",
    }
    payload.update(overrides)
    return payload


def _req(**overrides: object) -> dict:
    payload = {
        "schema_version": 1,
        "context": _ctx(),
        "arguments": {},
    }
    payload.update(overrides)
    return payload


class HostActionResultContractTests(unittest.TestCase):
    def test_valid_passed(self) -> None:
        result = normalize_host_action_result(
            {
                "schema_version": 1,
                "ok": True,
                "status": "passed",
                "summary": "ok",
                "errors": [],
                "warnings": [],
                "details": {},
            }
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.status, "passed")

    def test_valid_failed(self) -> None:
        result = normalize_host_action_result(
            {
                "schema_version": 1,
                "ok": False,
                "status": "failed",
                "summary": "no",
                "errors": ["x"],
                "warnings": [],
            }
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.status, "failed")

    def test_wrong_schema_version(self) -> None:
        result = normalize_host_action_result(
            {
                "schema_version": 2,
                "ok": True,
                "status": "passed",
                "summary": "x",
                "errors": [],
                "warnings": [],
            }
        )
        self.assertFalse(result.ok)
        self.assertIn("schema_version", result.summary)

    def test_missing_schema_version(self) -> None:
        result = normalize_host_action_result(
            {
                "ok": True,
                "status": "passed",
                "summary": "x",
                "errors": [],
                "warnings": [],
            }
        )
        self.assertFalse(result.ok)

    def test_ok_true_status_failed(self) -> None:
        result = normalize_host_action_result(
            {
                "schema_version": 1,
                "ok": True,
                "status": "failed",
                "summary": "x",
                "errors": [],
                "warnings": [],
            }
        )
        self.assertFalse(result.ok)
        self.assertIn("mismatch", result.summary)

    def test_ok_false_status_passed(self) -> None:
        result = normalize_host_action_result(
            {
                "schema_version": 1,
                "ok": False,
                "status": "passed",
                "summary": "x",
                "errors": [],
                "warnings": [],
            }
        )
        self.assertFalse(result.ok)
        self.assertIn("mismatch", result.summary)

    def test_unknown_status(self) -> None:
        result = normalize_host_action_result(
            {
                "schema_version": 1,
                "ok": True,
                "status": "banana",
                "summary": "x",
                "errors": [],
                "warnings": [],
            }
        )
        self.assertFalse(result.ok)

    def test_errors_not_list(self) -> None:
        result = normalize_host_action_result(
            {
                "schema_version": 1,
                "ok": False,
                "status": "failed",
                "summary": "x",
                "errors": "oops",
                "warnings": [],
            }
        )
        self.assertFalse(result.ok)

    def test_warnings_not_list(self) -> None:
        result = normalize_host_action_result(
            {
                "schema_version": 1,
                "ok": True,
                "status": "passed",
                "summary": "x",
                "errors": [],
                "warnings": "w",
            }
        )
        self.assertFalse(result.ok)

    def test_details_not_object(self) -> None:
        result = normalize_host_action_result(
            {
                "schema_version": 1,
                "ok": True,
                "status": "passed",
                "summary": "x",
                "errors": [],
                "warnings": [],
                "details": [],
            }
        )
        self.assertFalse(result.ok)

    def test_plain_text_stdout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "plain.py"
            script.write_text("print('done')\n", encoding="utf-8")
            result = self._run(root, script)
            self.assertFalse(result.ok)
            self.assertIn("JSON", result.summary)

    def test_empty_stdout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "empty.py"
            script.write_text("pass\n", encoding="utf-8")
            result = self._run(root, script)
            self.assertFalse(result.ok)
            self.assertIn("empty", result.summary)

    def test_nonzero_exit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "fail.py"
            script.write_text("raise SystemExit(3)\n", encoding="utf-8")
            result = self._run(root, script)
            self.assertFalse(result.ok)
            self.assertIn("exited 3", result.summary)

    def test_timeout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "slow.py"
            script.write_text(
                textwrap.dedent(
                    """\
                    import time
                    time.sleep(5)
                    """
                ),
                encoding="utf-8",
            )
            result = self._run(root, script, timeout_sec=0.2)
            self.assertFalse(result.ok)
            # Sandbox may deny process signals; either timeout or OSError is fail-closed.
            self.assertTrue(
                "timed out" in result.summary.lower()
                or "permission denied" in result.summary.lower(),
                result.summary,
            )

    def _run(
        self, root: Path, script: Path, *, timeout_sec: float | None = None
    ) -> HostActionResult:
        workspace = root / "workspace"
        workspace.mkdir()
        run_ctx = RunContext(
            project_root=root,
            workspace_root=workspace,
            run_id="r",
            stage_id="s",
            assignment_id="a",
            attempt=1,
            role="executor",
        )
        action = HostActionSpec(
            action_id="probe",
            command=sys.executable,
            args=[str(script)],
            tool_timeout_sec=30,
        )
        return run_host_action(
            action,
            run_ctx=run_ctx,
            project_root=root,
            timeout_sec=timeout_sec,
        )


class HostActionRequestContractTests(unittest.TestCase):
    def test_valid_request(self) -> None:
        context, arguments = parse_host_request(_req())
        self.assertEqual(context["run_id"], "run-1")
        self.assertEqual(arguments, {})

    def test_build_host_request_envelope(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            run_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="r",
                stage_id="s",
                assignment_id="a",
                attempt=2,
                role="reviewer",
                metadata={"k": 1},
            )
            envelope = build_host_request(
                run_ctx, project_root=root, arguments={"p": 1}
            )
            self.assertEqual(envelope["schema_version"], 1)
            self.assertNotIn("schema_version", envelope["context"])
            context, arguments = parse_host_request(envelope)
            self.assertEqual(context["attempt"], 2)
            self.assertEqual(arguments, {"p": 1})

    def test_missing_run_id(self) -> None:
        with self.assertRaises(ValueError):
            parse_host_request(_req(context=_ctx(run_id="")))

    def test_missing_workspace(self) -> None:
        with self.assertRaises(ValueError):
            parse_host_request(_req(context=_ctx(workspace="")))

    def test_attempt_bool(self) -> None:
        with self.assertRaises(ValueError):
            parse_host_request(_req(context=_ctx(attempt=True)))

    def test_attempt_non_positive(self) -> None:
        with self.assertRaises(ValueError):
            parse_host_request(_req(context=_ctx(attempt=0)))

    def test_metadata_not_object(self) -> None:
        with self.assertRaises(ValueError):
            parse_host_request(_req(context=_ctx(metadata=[])))

    def test_arguments_not_object(self) -> None:
        with self.assertRaises(ValueError):
            parse_host_request(_req(arguments=[]))

    def test_invalid_schema_version(self) -> None:
        with self.assertRaises(ValueError):
            parse_host_request(_req(schema_version=2))


if __name__ == "__main__":
    unittest.main()
