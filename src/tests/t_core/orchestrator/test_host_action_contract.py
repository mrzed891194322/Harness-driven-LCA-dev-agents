"""Strict Host Action request/result wire-protocol tests."""

from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.runtime.context import RunContext
from core.runtime.host_action import (
    HostActionExecutionError,
    HostActionProtocolError,
    HostActionResult,
    build_host_request,
    normalize_host_action_result,
    run_host_action,
)
from core.workflow.config.models import HostActionSpec
from harness.tools.host_action.protocol import parse_host_request


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
        "handoff_path": "records/handoffs/x.json",
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
        with self.assertRaises(HostActionProtocolError):
            normalize_host_action_result(
                {
                    "schema_version": 2,
                    "ok": True,
                    "status": "passed",
                    "summary": "x",
                    "errors": [],
                    "warnings": [],
                }
            )

    def test_missing_schema_version(self) -> None:
        with self.assertRaises(HostActionProtocolError):
            normalize_host_action_result(
                {
                    "ok": True,
                    "status": "passed",
                    "summary": "x",
                    "errors": [],
                    "warnings": [],
                }
            )

    def test_ok_true_status_failed(self) -> None:
        with self.assertRaises(HostActionProtocolError) as ctx:
            normalize_host_action_result(
                {
                    "schema_version": 1,
                    "ok": True,
                    "status": "failed",
                    "summary": "x",
                    "errors": [],
                    "warnings": [],
                }
            )
        self.assertIn("mismatch", str(ctx.exception))

    def test_ok_false_status_passed(self) -> None:
        with self.assertRaises(HostActionProtocolError) as ctx:
            normalize_host_action_result(
                {
                    "schema_version": 1,
                    "ok": False,
                    "status": "passed",
                    "summary": "x",
                    "errors": [],
                    "warnings": [],
                }
            )
        self.assertIn("mismatch", str(ctx.exception))

    def test_ok_true_with_errors(self) -> None:
        with self.assertRaises(HostActionProtocolError):
            normalize_host_action_result(
                {
                    "schema_version": 1,
                    "ok": True,
                    "status": "passed",
                    "summary": "x",
                    "errors": ["nope"],
                    "warnings": [],
                }
            )

    def test_unknown_result_field(self) -> None:
        with self.assertRaises(HostActionProtocolError):
            normalize_host_action_result(
                {
                    "schema_version": 1,
                    "ok": True,
                    "status": "passed",
                    "summary": "x",
                    "errors": [],
                    "warnings": [],
                    "extra": 1,
                }
            )

    def test_unknown_status(self) -> None:
        with self.assertRaises(HostActionProtocolError):
            normalize_host_action_result(
                {
                    "schema_version": 1,
                    "ok": True,
                    "status": "banana",
                    "summary": "x",
                    "errors": [],
                    "warnings": [],
                }
            )

    def test_errors_not_list(self) -> None:
        with self.assertRaises(HostActionProtocolError):
            normalize_host_action_result(
                {
                    "schema_version": 1,
                    "ok": False,
                    "status": "failed",
                    "summary": "x",
                    "errors": "oops",
                    "warnings": [],
                }
            )

    def test_warnings_not_list(self) -> None:
        with self.assertRaises(HostActionProtocolError):
            normalize_host_action_result(
                {
                    "schema_version": 1,
                    "ok": True,
                    "status": "passed",
                    "summary": "x",
                    "errors": [],
                    "warnings": "w",
                }
            )

    def test_details_not_object(self) -> None:
        with self.assertRaises(HostActionProtocolError):
            normalize_host_action_result(
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

    def test_plain_text_stdout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "plain.py"
            script.write_text("print('done')\n", encoding="utf-8")
            with self.assertRaises(HostActionProtocolError) as ctx:
                self._run(root, script)
            self.assertIn("JSON", str(ctx.exception))

    def test_empty_stdout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "empty.py"
            script.write_text("pass\n", encoding="utf-8")
            with self.assertRaises(HostActionProtocolError) as ctx:
                self._run(root, script)
            self.assertIn("empty", str(ctx.exception))

    def test_nonzero_exit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "fail.py"
            script.write_text("raise SystemExit(3)\n", encoding="utf-8")
            with self.assertRaises(HostActionExecutionError) as ctx:
                self._run(root, script)
            self.assertIn("exited 3", str(ctx.exception))

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
            with self.assertRaises(HostActionExecutionError) as ctx:
                self._run(root, script, timeout_sec=0.2)
            message = str(ctx.exception).lower()
            self.assertTrue(
                "timed out" in message or "permission denied" in message,
                message,
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
            timeout_sec=30,
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

    def test_unknown_request_field(self) -> None:
        with self.assertRaises(ValueError):
            parse_host_request(_req(extra=True))

    def test_unknown_context_field(self) -> None:
        with self.assertRaises(ValueError):
            parse_host_request(_req(context=_ctx(foo="bar")))

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
