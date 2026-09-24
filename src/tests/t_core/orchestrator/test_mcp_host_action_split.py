"""Generic MCP vs Host Action split: Agent sees MCP only; Core runs Host Actions."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from core.runtime.capabilities import base_capabilities
from core.runtime.context import RunContext
from core.runtime.host_action import run_host_action
from core.runtime.mcp_host import invoke_tool
from core.workflow.config.loader import load_workflow
from core.workflow.execution.session_bind import build_session_config
from tests.conftest import PROJECT_ROOT
from tests.support.minimal_workflow import (
    write_fake_host_action,
    write_fake_mcp_server,
    write_minimal_workflow,
)


class McpHostActionSplitTests(unittest.TestCase):
    def test_agent_mcp_list_excludes_host_action_and_core_runs_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                workflow_id="split",
                filename="split.yaml",
                tool_command=sys.executable,
            )
            mcp_script = write_fake_mcp_server(root)
            ha_script = write_fake_host_action(root)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["registry"]["tools"]["mcp"]["probe"]["args"] = [str(mcp_script)]
            payload["registry"]["tools"]["host_action"]["verify"]["args"] = [
                str(ha_script)
            ]
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            self.assertIn("probe", workflow.mcp_tools)
            self.assertIn("verify", workflow.host_actions)
            self.assertNotIn("verify", workflow.mcp_tools)
            self.assertNotIn("probe", workflow.host_actions)

            workspace = root / "workspace"
            workspace.mkdir()
            bundle = workflow.bundles["s1.executor"]
            config = build_session_config(
                workflow,
                bundle,
                project_root=root,
                workspace_root=workspace,
                worker="codex",
                model="test-model",
                stage=workflow.stages[0],
                assignment=workflow.assignments["s1.executor"],
                run_id="run-split",
                attempt=1,
            )
            self.assertEqual(set(config.mcp_servers), {"probe"})
            self.assertNotIn("verify", config.mcp_servers)

            run_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="run-split",
                stage_id="s1",
                assignment_id="s1.executor",
                attempt=1,
                role="executor",
                metadata={"token": "ctx-ok"},
            )
            echo = invoke_tool(
                workflow.mcp_tools["probe"],
                "echo",
                {"ping": True},
                run_ctx=run_ctx,
                project_root=root,
            )
            self.assertTrue(echo.ok, echo.summary)
            self.assertEqual(echo.summary, "echo")

            result = run_host_action(
                workflow.host_actions["verify"],
                run_ctx=run_ctx,
                project_root=root,
                arguments={"profile": "demo"},
            )
            self.assertTrue(result.ok, result.summary)
            self.assertEqual(result.status, "passed")
            self.assertEqual(result.details.get("run_id"), "run-split")
            self.assertEqual(
                (result.details.get("arguments") or {}).get("profile"), "demo"
            )
            self.assertEqual(bundle.acceptance_checks[0].action, "verify")

    def test_three_entrypoints_start_with_project_pythonpath(self) -> None:
        entries = (
            "harness/tools/mcp/lca_artifacts/main.py",
            "harness/tools/mcp/control_openlca/workflow_mcp.py",
            "harness/tools/host_action/lca_artifacts/main.py",
        )
        for relative in entries:
            path = PROJECT_ROOT / relative
            self.assertTrue(path.is_file(), relative)
            if relative.endswith("host_action/lca_artifacts/main.py"):
                proc = subprocess.run(
                    [sys.executable, str(path), "--help"],
                    cwd=PROJECT_ROOT,
                    env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
                    capture_output=True,
                    text=True,
                    timeout=30,
                    input="",
                )
                self.assertEqual(proc.returncode, 2, proc.stderr)
            else:
                code = (
                    "import importlib.util, pathlib, sys\n"
                    f"path = pathlib.Path({str(path)!r})\n"
                    "spec = importlib.util.spec_from_file_location('entry', path)\n"
                    "mod = importlib.util.module_from_spec(spec)\n"
                    "sys.modules['entry'] = mod\n"
                    "spec.loader.exec_module(mod)\n"
                    "print('ok')\n"
                )
                proc = subprocess.run(
                    [sys.executable, "-c", code],
                    cwd=PROJECT_ROOT,
                    env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("ok", proc.stdout)


if __name__ == "__main__":
    unittest.main()
