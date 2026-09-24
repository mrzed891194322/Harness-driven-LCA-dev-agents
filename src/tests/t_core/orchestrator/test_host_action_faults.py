"""Fault-injection: HostActionError is system failure; business ok=false retries."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime.capabilities import base_capabilities
from core.runtime.host_action import (
    HostActionExecutionError,
    HostActionProtocolError,
    HostActionResult,
)
from core.workflow.config.loader import load_workflow
from core.workflow.execution.runner import (
    OrchestratorRuntime,
    initial_state,
    run_workflow,
)
from core.workflow.persistence.checkpoint import open_store
from tests.support.minimal_workflow import write_minimal_workflow
from tests.support.scripted_session import (
    ScriptedSessionClient,
    _passing_run_host_action,
)


def _script_ok() -> dict:
    return {
        ("s1", "executor", 1): {
            "status": "ok",
            "write": ["workspace/out.txt"],
        },
        ("s1", "reviewer", 1): {"status": "passed"},
        ("s1", "executor", 2): {
            "status": "ok",
            "write": ["workspace/out.txt"],
        },
        ("s1", "reviewer", 2): {"status": "passed"},
    }


class HostActionFaultInjectionTests(unittest.TestCase):
    def _run(
        self,
        *,
        side_effect,
        max_attempts: int = 2,
        handoff_checks: list | None = None,
        on_reviewer_passed: list | None = None,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                max_attempts=max_attempts,
                handoff_checks=handoff_checks,
                on_reviewer_passed=on_reviewer_passed,
            )
            # Patch max_attempts on stage via YAML rewrite if helper supports it.
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            workspace = root / "workspace"
            workspace.mkdir()
            client = ScriptedSessionClient(workspace, _script_ok())
            runtime = OrchestratorRuntime(
                workflow,
                project_root=root,
                workspace_root=workspace,
                session_client=client,
                worker="codex",
                model="test",
                capabilities=base_capabilities(),
            )
            with (
                open_store(workspace) as store,
                patch(
                    "core.workflow.execution.runner.run_host_action",
                    side_effect=side_effect,
                ),
            ):
                result = run_workflow(
                    runtime,
                    initial_state(
                        run_id="fault",
                        task="generic",
                        worker="codex",
                        workflow=workflow,
                    ),
                    store,
                )
            return result, client

    def test_acceptance_business_failure_retries_and_burns_attempt(self) -> None:
        calls = {"n": 0}

        def selective(action, **kwargs):
            if getattr(action, "action_id", "") == "verify":
                calls["n"] += 1
                if calls["n"] == 1:
                    return HostActionResult(
                        ok=False,
                        status="failed",
                        summary="biz",
                        errors=["gap"],
                    )
            return _passing_run_host_action(action, **kwargs)

        result, client = self._run(side_effect=selective, max_attempts=2)
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(calls["n"], 2)
        labels = [label for _sid, label in client.turns]
        self.assertIn("s1:executor:2", labels)

    def test_acceptance_execution_error_fails_run_without_retry(self) -> None:
        attempts_seen: list[int] = []

        def selective(action, *, run_ctx=None, **kwargs):
            if getattr(action, "action_id", "") == "verify":
                attempts_seen.append(int(getattr(run_ctx, "attempt", 0) or 0))
                raise HostActionExecutionError("exited 1")
            return _passing_run_host_action(action, run_ctx=run_ctx, **kwargs)

        result, client = self._run(side_effect=selective, max_attempts=3)
        self.assertEqual(result["status"], "failed")
        self.assertIn("基础设施", result["status_reason"])
        self.assertEqual(attempts_seen, [1])
        labels = [label for _sid, label in client.turns]
        self.assertEqual(labels, ["s1:executor:1"])

    def test_acceptance_protocol_error_fails_run_without_retry(self) -> None:
        def selective(action, **kwargs):
            if getattr(action, "action_id", "") == "verify":
                raise HostActionProtocolError("bad wire")
            return _passing_run_host_action(action, **kwargs)

        result, client = self._run(side_effect=selective, max_attempts=3)
        self.assertEqual(result["status"], "failed")
        self.assertIn("协议", result["status_reason"])
        labels = [label for _sid, label in client.turns]
        self.assertEqual(labels, ["s1:executor:1"])

    def test_handoff_business_invalid_repairs_without_system_fail(self) -> None:
        calls = {"n": 0}

        def selective(action, **kwargs):
            if getattr(action, "action_id", "") == "handoff_probe":
                calls["n"] += 1
                if calls["n"] == 1:
                    return HostActionResult(
                        ok=False,
                        status="failed",
                        summary="bad handoff",
                        errors=["field x"],
                    )
            return _passing_run_host_action(action, **kwargs)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                handoff_checks=[
                    {"id": "handoff", "action": "handoff_probe", "arguments": {}}
                ],
                host_action_id="verify",
            )
            # Register second host action id used by handoff check.
            import yaml

            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["registry"]["tools"]["host_action"]["handoff_probe"] = dict(
                payload["registry"]["tools"]["host_action"]["verify"]
            )
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            workspace = root / "workspace"
            workspace.mkdir()
            script = _script_ok()
            # Protocol repair reuses the same attempt; provide a second writer turn.
            script[("s1", "executor", 1)] = [
                {"status": "ok", "write": ["workspace/out.txt"]},
                {"status": "ok", "write": ["workspace/out.txt"]},
            ]
            client = ScriptedSessionClient(workspace, script)
            runtime = OrchestratorRuntime(
                workflow,
                project_root=root,
                workspace_root=workspace,
                session_client=client,
                worker="codex",
                model="test",
                capabilities=base_capabilities(),
            )
            with (
                open_store(workspace) as store,
                patch(
                    "core.workflow.execution.runner.run_host_action",
                    side_effect=selective,
                ),
            ):
                result = run_workflow(
                    runtime,
                    initial_state(
                        run_id="fault-handoff",
                        task="generic",
                        worker="codex",
                        workflow=workflow,
                    ),
                    store,
                )
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(calls["n"], 2)

    def test_handoff_host_action_crash_fails_without_protocol_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                handoff_checks=[
                    {"id": "handoff", "action": "handoff_probe", "arguments": {}}
                ],
            )
            import yaml

            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["registry"]["tools"]["host_action"]["handoff_probe"] = dict(
                payload["registry"]["tools"]["host_action"]["verify"]
            )
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            workspace = root / "workspace"
            workspace.mkdir()
            client = ScriptedSessionClient(workspace, _script_ok())

            def selective(action, **kwargs):
                if getattr(action, "action_id", "") == "handoff_probe":
                    raise HostActionExecutionError("crash")
                return _passing_run_host_action(action, **kwargs)

            runtime = OrchestratorRuntime(
                workflow,
                project_root=root,
                workspace_root=workspace,
                session_client=client,
                worker="codex",
                model="test",
                capabilities=base_capabilities(),
            )
            with (
                open_store(workspace) as store,
                patch(
                    "core.workflow.execution.runner.run_host_action",
                    side_effect=selective,
                ),
            ):
                result = run_workflow(
                    runtime,
                    initial_state(
                        run_id="fault-handoff-crash",
                        task="generic",
                        worker="codex",
                        workflow=workflow,
                    ),
                    store,
                )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(int(result.get("protocol_repairs") or 0), 0)
        self.assertIn("基础设施", result["status_reason"])

    def test_reviewer_recheck_crash_fails_without_writer_retry(self) -> None:
        phase = {"accept": 0}

        def selective(action, *, run_ctx=None, **kwargs):
            role = str(getattr(run_ctx, "role", "") or "")
            action_id = str(getattr(action, "action_id", "") or "")
            if action_id == "verify" and role == "reviewer":
                raise HostActionExecutionError("recheck boom")
            if action_id == "verify":
                phase["accept"] += 1
            return _passing_run_host_action(action, run_ctx=run_ctx, **kwargs)

        result, client = self._run(side_effect=selective, max_attempts=3)
        self.assertEqual(result["status"], "failed")
        self.assertIn("审查重验", result["status_reason"])
        labels = [label for _sid, label in client.turns]
        self.assertEqual(labels, ["s1:executor:1", "s1:reviewer:1"])

    def test_lifecycle_host_action_crash_fails_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                on_reviewer_passed=[
                    {"id": "hook", "action": "record_hook", "arguments": {}}
                ],
            )
            import yaml

            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["registry"]["tools"]["host_action"]["record_hook"] = dict(
                payload["registry"]["tools"]["host_action"]["verify"]
            )
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            workspace = root / "workspace"
            workspace.mkdir()
            client = ScriptedSessionClient(workspace, _script_ok())

            def selective(action, **kwargs):
                if getattr(action, "action_id", "") == "record_hook":
                    raise HostActionProtocolError("lifecycle wire bad")
                return _passing_run_host_action(action, **kwargs)

            runtime = OrchestratorRuntime(
                workflow,
                project_root=root,
                workspace_root=workspace,
                session_client=client,
                worker="codex",
                model="test",
                capabilities=base_capabilities(),
            )
            with (
                open_store(workspace) as store,
                patch(
                    "core.workflow.execution.runner.run_host_action",
                    side_effect=selective,
                ),
            ):
                result = run_workflow(
                    runtime,
                    initial_state(
                        run_id="fault-life",
                        task="generic",
                        worker="codex",
                        workflow=workflow,
                    ),
                    store,
                )
        self.assertEqual(result["status"], "failed")
        self.assertIn("lifecycle", result["status_reason"])


if __name__ == "__main__":
    unittest.main()
