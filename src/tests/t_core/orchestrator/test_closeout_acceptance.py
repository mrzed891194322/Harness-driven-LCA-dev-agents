"""Closeout acceptance regressions for MCP host checks / lifecycle actions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime.capabilities import base_capabilities
from core.runtime.mcp_host import CheckResult
from core.workflow.config.loader import load_workflow
from core.workflow.execution.runner import (
    OrchestratorRuntime,
    initial_state,
    run_workflow,
)
from core.workflow.main import peek_tool_ids
from core.workflow.persistence.checkpoint import open_store
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.minimal_workflow import write_minimal_workflow
from tests.support.scripted_session import (
    ScriptedSessionClient,
    _happy_script,
    _passing_invoke_tool,
)


class CapabilitiesCompositionTests(unittest.TestCase):
    def test_generic_workflow_gets_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            binding = workflow.bundles["s1.executor"].knowledge_sources[0]
            self.assertEqual(binding.provider, "local_files")

    def test_peek_tool_ids_not_providers(self) -> None:
        ids = peek_tool_ids(WORKFLOWS / "LCA-main.yaml", project_root=PROJECT_ROOT)
        self.assertEqual(ids, ["control_openlca", "lca_artifacts"])


class ReviewerPassGuardTests(unittest.TestCase):
    def test_lifecycle_runs_after_mapping_reviewer_pass(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        calls: list[str] = []

        def track(tool, method, arguments, **kwargs):
            calls.append(method)
            return _passing_invoke_tool(tool, method, arguments, **kwargs)

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
                patch("core.workflow.execution.runner.invoke_tool", side_effect=track),
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
        self.assertIn("record_acceptance", calls)


class HostCheckRetryTests(unittest.TestCase):
    def test_failed_acceptance_retries_writer(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        mapping_validate = {"n": 0}

        def selective(tool, method, arguments, **kwargs):
            profile = str((arguments or {}).get("profile") or "")
            if method == "validate_artifacts" and profile == "mapping":
                mapping_validate["n"] += 1
                if mapping_validate["n"] == 1:
                    return CheckResult(
                        ok=False,
                        status="failed",
                        summary="gap",
                        errors=["item_id gap"],
                    )
            return _passing_invoke_tool(tool, method, arguments, **kwargs)

        script = _happy_script()
        script[("03-dataset-mapping", "executor", 2)] = {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/process-mapping.json",
                "workspace/outputs/LCI/",
            ],
        }
        script[("03-dataset-mapping", "reviewer", 2)] = {"status": "passed"}
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            client = ScriptedSessionClient(workspace, script)
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
                    "core.workflow.execution.runner.invoke_tool", side_effect=selective
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
        mapping = [
            label
            for _sid, label in client.turns
            if label.startswith("03-dataset-mapping")
        ]
        self.assertEqual(
            mapping,
            [
                "03-dataset-mapping:executor:1",
                "03-dataset-mapping:executor:2",
                "03-dataset-mapping:reviewer:2",
            ],
        )


if __name__ == "__main__":
    unittest.main()
