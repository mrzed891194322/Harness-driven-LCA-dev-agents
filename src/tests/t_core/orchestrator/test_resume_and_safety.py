"""Resume / safety regressions that remain valid under MCP-only core."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime.capabilities import base_capabilities
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
    _passing_invoke_tool,
)


class ReviewOnlyTopologyTests(unittest.TestCase):
    def test_review_only_empty_checks_ok(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        intake = workflow.bundles["01-intake-gate.reviewer"]
        self.assertEqual(intake.acceptance_checks, [])
        self.assertEqual(intake.role, "reviewer")


class DuplicateIdsTests(unittest.TestCase):
    def test_duplicate_acceptance_tool_reference_ok_when_tool_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                acceptance=[
                    {"id": "a", "tool": "probe", "call": "validate", "arguments": {}},
                    {"id": "b", "tool": "probe", "call": "get_state", "arguments": {}},
                ],
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            self.assertEqual(len(workflow.bundles["s1.executor"].acceptance_checks), 2)

    def test_unknown_acceptance_tool_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                acceptance=[
                    {"id": "a", "tool": "missing", "call": "validate", "arguments": {}}
                ],
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=base_capabilities())


class OutputTrailingSlashTests(unittest.TestCase):
    def test_directory_output_contract(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        outs = workflow.bundles["03-dataset-mapping.executor"].stage_spec.outputs
        kinds = {item.path: item.kind for item in outs}
        self.assertEqual(kinds.get("workspace/outputs/LCI"), "directory")


class FrozenModelTests(unittest.TestCase):
    def test_session_config_uses_runtime_model_not_env(self) -> None:
        from core.workflow.execution.session_bind import build_session_config

        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        stage = workflow.stage_by_id("02-inventory-extraction")
        assignment = workflow.assignments["02-inventory-extraction.executor"]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            config = build_session_config(
                workflow,
                workflow.bundles[assignment.assignment_id],
                project_root=PROJECT_ROOT,
                workspace_root=workspace,
                worker="codex",
                model="frozen-model",
                stage=stage,
                assignment=assignment,
                run_id="r",
                attempt=1,
            )
        self.assertEqual(config.model, "frozen-model")


class ImplementationFingerprintTests(unittest.TestCase):
    def test_implementation_change_rejects_resume(self) -> None:
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
                model="m",
            )
            with self.assertRaises(ValueError):
                assert_runtime_config_matches(
                    workspace,
                    "run-1",
                    workflow,
                    project_root=PROJECT_ROOT,
                    worker="pi",
                    model="m",
                )


class HappyResumeSmokeTests(unittest.TestCase):
    def test_completed_run_smoke(self) -> None:
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
                    "core.workflow.execution.runner.invoke_tool",
                    side_effect=_passing_invoke_tool,
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


class SymlinkSafetyTests(unittest.TestCase):
    def test_task_spec_symlink_removed_from_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("task_spec", text)
            self.assertNotIn("runtime_spec", text)


if __name__ == "__main__":
    unittest.main()
