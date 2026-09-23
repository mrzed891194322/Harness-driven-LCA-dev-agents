from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from core.runtime.capabilities import base_capabilities
from core.runtime.context import RunContext
from core.runtime.mcp_host import CheckResult
from core.workflow.config.loader import load_workflow
from core.workflow.execution.session_bind import build_session_config
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.minimal_workflow import (
    write_fake_mcp_server,
    write_minimal_workflow,
    write_stage_spec,
    write_tree,
)


class GenericRuntimeTests(unittest.TestCase):
    def test_fake_workflow_without_lca_stage_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fake_mcp_server(root)
            path = write_minimal_workflow(
                root,
                workflow_id="fake",
                filename="fake.yaml",
                stage_id="alpha-step",
            )
            # Remap assignment ids to alpha.* for clarity
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["stages"][0]["steps"] = [
                {"assignment": "alpha.executor"},
                {"assignment": "alpha.reviewer"},
            ]
            payload["assignments"] = {
                "alpha.executor": payload["assignments"]["alpha-step.executor"],
                "alpha.reviewer": payload["assignments"]["alpha-step.reviewer"],
            }
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            bundle = workflow.bundles["alpha.executor"]
            self.assertEqual(bundle.stage_id, "alpha-step")
            self.assertEqual(bundle.acceptance_checks[0].id, "ping")

    def test_acceptance_check_mocked_via_invoke_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root, stage_id="inv-phase")
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            check = workflow.bundles["inv-phase.executor"].acceptance_checks[0]
            run_ctx = RunContext(
                project_root=root,
                workspace_root=root / "workspace",
                run_id="r1",
                stage_id="inv-phase",
                assignment_id="inv-phase.executor",
                attempt=1,
                role="executor",
                metadata={},
            )
            with patch(
                "core.runtime.mcp_host.invoke_tool",
                return_value=CheckResult(ok=True, status="passed", summary="ok"),
            ) as mocked:
                from core.runtime import mcp_host

                result = mcp_host.invoke_tool(
                    workflow.tools[check.tool],
                    check.call,
                    dict(check.arguments),
                    run_ctx=run_ctx,
                    project_root=root,
                )
            self.assertTrue(result.ok)
            mocked.assert_called_once()

    def test_tool_runtime_without_whitelist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_tree(root)
            write_stage_spec(root, stage_id="s1", acceptance=[], tool="fake_tool")
            (root / "harness" / "tools" / "fake_tool").mkdir(parents=True)
            (root / "harness" / "tools" / "fake_tool" / "main.py").write_text(
                "print('ok')\n", encoding="utf-8"
            )
            (root / "harness" / "tools" / "plain_tool").mkdir(parents=True)
            (root / "harness" / "tools" / "plain_tool" / "main.py").write_text(
                "print('ok')\n", encoding="utf-8"
            )
            payload = {
                "id": "runtime-test",
                "registry": {
                    "rules": {
                        "workspace_boundary": "harness/rules/project/write-boundary.md",
                        "runtime": "harness/rules/project/runtime.md",
                        "paths": "harness/rules/project/paths.md",
                    },
                    "tools": {
                        "fake_tool": {
                            "transport": "stdio",
                            "command": "python",
                            "args": ["harness/tools/fake_tool/main.py"],
                            "runtime": {
                                "run_context_env": True,
                                "context_file": True,
                                "env_prefix": "HARNESS",
                            },
                        },
                        "plain_tool": {
                            "transport": "stdio",
                            "command": "python",
                            "args": ["harness/tools/plain_tool/main.py"],
                        },
                    },
                    "knowledge": {
                        "workspace_knowledge": {
                            "kind": "local_dir",
                            "path": "harness/knowledge/",
                            "provider": "local_files",
                        }
                    },
                },
                "defaults": {
                    "rules": ["workspace_boundary", "runtime", "paths"],
                    "knowledge": ["workspace_knowledge"],
                },
                "stages": [
                    {
                        "id": "s1",
                        "spec": "harness/specs/s1/spec.yaml",
                        "steps": [
                            {"assignment": "s1.executor"},
                            {"assignment": "s1.reviewer"},
                        ],
                    }
                ],
                "assignments": {
                    "s1.executor": {
                        "role": "executor",
                        "tools": ["fake_tool", "plain_tool"],
                    },
                    "s1.reviewer": {"role": "reviewer", "tools": []},
                },
            }
            path = root / "harness" / "runtime-test.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            workspace = root / "workspace"
            workspace.mkdir()
            config = build_session_config(
                workflow,
                workflow.bundles["s1.executor"],
                project_root=root,
                workspace_root=workspace,
                worker="codex",
                model="test-model",
                stage=workflow.stages[0],
                assignment=workflow.assignments["s1.executor"],
                run_id="run-1",
                attempt=1,
            )
            server = config.mcp_servers["fake_tool"]
            self.assertIn("HARNESS_RUN_ID", server["env"])
            self.assertIn("--context-file", server["args"])
            plain = config.mcp_servers["plain_tool"]
            self.assertNotIn("HARNESS_RUN_ID", plain.get("env", {}))

    def test_unknown_check_tool_fail_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                acceptance=[
                    {
                        "id": "missing",
                        "tool": "nope",
                        "call": "validate",
                        "arguments": {},
                    }
                ],
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=base_capabilities())

    def test_lca_main_lifecycle_on_bundle(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        inventory = workflow.bundles["02-inventory-extraction.reviewer"]
        mapping = workflow.bundles["03-dataset-mapping.reviewer"]
        report = workflow.bundles["04-openlca-reporting.reviewer"]
        self.assertEqual(inventory.on_reviewer_passed, [])
        self.assertEqual(len(mapping.on_reviewer_passed), 1)
        self.assertEqual(mapping.on_reviewer_passed[0].call, "record_acceptance")
        self.assertEqual(report.on_reviewer_passed, [])


if __name__ == "__main__":
    unittest.main()
