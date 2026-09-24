"""Audit / fingerprint / YAML strictness closeouts for MCP-only core."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from core.runtime.capabilities import base_capabilities
from core.runtime.host_action import HostActionResult
from core.workflow.config.loader import load_workflow
from core.workflow.execution.runner import (
    OrchestratorRuntime,
    initial_state,
    run_workflow,
)
from core.workflow.persistence.checkpoint import open_store
from core.workflow.persistence.config_fingerprint import (
    assert_runtime_config_matches,
    write_runtime_config,
)
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.minimal_workflow import write_minimal_workflow
from tests.support.scripted_session import (
    ScriptedSessionClient,
    _happy_script,
    _passing_run_host_action,
)


class StrictYamlAndTypeTests(unittest.TestCase):
    def test_invalid_max_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["max_attempts"] = 0
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=base_capabilities())

    def test_task_spec_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["assignments"]["s1.executor"]["task_spec"] = "x.md"
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=base_capabilities())


class EnvTimeoutFingerprintTests(unittest.TestCase):
    def test_env_and_timeout_value_change_fingerprint(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            write_runtime_config(
                workspace,
                "run-1",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="m1",
            )
            with self.assertRaises(ValueError):
                assert_runtime_config_matches(
                    workspace,
                    "run-1",
                    workflow,
                    project_root=PROJECT_ROOT,
                    worker="codex",
                    model="m2",
                )


class ReviewNoteGateTests(unittest.TestCase):
    def test_guard_success_note_accepted(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            client = ScriptedSessionClient(workspace, _happy_script())
            runtime = OrchestratorRuntime(
                workflow,
                project_root=PROJECT_ROOT,
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
                    side_effect=_passing_run_host_action,
                ),
            ):
                result = run_workflow(
                    runtime,
                    initial_state(
                        run_id="r1",
                        task="whole-lca",
                        worker="codex",
                        workflow=workflow,
                    ),
                    store,
                )
            self.assertEqual(result["status"], "completed")
            note = workspace / "records" / "reviews" / "03-dataset-mapping-1.md"
            self.assertTrue(note.is_file())
            self.assertIn("accepted", note.read_text(encoding="utf-8"))


class HookFailClosedTests(unittest.TestCase):
    def test_lifecycle_failure_fails_run_without_writer_retry(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )

        def selective(
            action,
            *,
            run_ctx=None,
            project_root=None,
            arguments=None,
            timeout_sec=None,
            **kwargs,
        ):
            if getattr(action, "action_id", None) == "record_acceptance":
                return HostActionResult(
                    ok=False, status="failed", summary="boom", errors=["boom"]
                )
            return _passing_run_host_action(
                action, run_ctx=run_ctx, arguments=arguments
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            client = ScriptedSessionClient(workspace, _happy_script())
            runtime = OrchestratorRuntime(
                workflow,
                project_root=PROJECT_ROOT,
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
                        run_id="r1",
                        task="whole-lca",
                        worker="codex",
                        workflow=workflow,
                    ),
                    store,
                )
        self.assertEqual(result["status"], "failed")
        mapping_exec = [
            label
            for _sid, label in client.turns
            if label.startswith("03-dataset-mapping:executor")
        ]
        self.assertEqual(mapping_exec, ["03-dataset-mapping:executor:1"])


if __name__ == "__main__":
    unittest.main()
