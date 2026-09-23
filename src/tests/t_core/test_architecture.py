"""Architecture guards: core stays harness-agnostic; MCP-only host checks."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from core.runtime.capabilities import base_capabilities
from core.runtime.mcp_host import invoke_tool
from core.workflow.config.loader import load_workflow
from core.workflow.main import peek_tool_ids
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.minimal_workflow import write_fake_mcp_server, write_minimal_workflow

CORE_ROOT = PROJECT_ROOT / "src" / "core"
HARNESS_ROOT = PROJECT_ROOT / "harness"
BANNED_IMPORT_PREFIXES = (
    "domains",
    "services",
    "schema",
    "gui",
    "scripts",
    "harness",
)
HARNESS_ROOT_ALLOWLIST = frozenset(
    {
        "LCA-main.yaml",
        "LCA-revise.yaml",
        "knowledge",
        "tools",
        "rules",
        "specs",
    }
)


def _src_env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")}


def _iter_core_py_files() -> list[Path]:
    return sorted(p for p in CORE_ROOT.rglob("*.py") if p.is_file())


def _module_prefixes(node: ast.AST) -> list[str]:
    names: list[str] = []
    if isinstance(node, ast.Import):
        names.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        names.append(node.module)
    return names


def _is_banned(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in BANNED_IMPORT_PREFIXES
    )


class CoreArchitectureTests(unittest.TestCase):
    def test_core_sources_do_not_hard_import_harness_or_app_layers(self) -> None:
        violations: list[str] = []
        for path in _iter_core_py_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                for module in _module_prefixes(node):
                    if _is_banned(module):
                        rel = path.relative_to(PROJECT_ROOT)
                        violations.append(f"{rel}: import {module}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_core_has_no_providers_compose_modules(self) -> None:
        self.assertFalse((CORE_ROOT / "runtime" / "providers.py").exists())
        self.assertFalse((CORE_ROOT / "runtime" / "compose.py").exists())

    def test_importing_core_workflow_does_not_load_harness(self) -> None:
        code = """
import sys
from core.workflow.main import main, peek_tool_ids
from core.runtime.capabilities import base_capabilities
assert callable(main) and callable(peek_tool_ids)
caps = base_capabilities()
assert caps is not None
banned = ("domains", "services", "schema", "harness", "gui", "scripts")
loaded = [
    name for name in sys.modules
    if any(name == b or name.startswith(b + ".") for b in banned)
]
assert not loaded, loaded
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            env=_src_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_workflow_cli_requires_workflow_flag_not_task(self) -> None:
        help_result = subprocess.run(
            [sys.executable, "src/scripts/workflow.py", "--help"],
            cwd=PROJECT_ROOT,
            env=_src_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--workflow", help_result.stdout)
        self.assertNotIn("--task", help_result.stdout)

        missing = subprocess.run(
            [sys.executable, "src/scripts/workflow.py"],
            cwd=PROJECT_ROOT,
            env=_src_env(),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(missing.returncode, 0)
        combined = (missing.stderr + missing.stdout).lower()
        self.assertIn("workflow", combined)

    def test_harness_index_yaml_absent(self) -> None:
        self.assertFalse((HARNESS_ROOT / "index.yaml").exists())

    def test_harness_specs_have_no_markdown(self) -> None:
        md_files = sorted(HARNESS_ROOT.joinpath("specs").rglob("*.md"))
        self.assertEqual(md_files, [], "\n".join(str(p) for p in md_files))

    def test_harness_root_allowlist(self) -> None:
        names = {p.name for p in HARNESS_ROOT.iterdir()}
        unexpected = sorted(names - HARNESS_ROOT_ALLOWLIST)
        self.assertEqual(
            unexpected,
            [],
            f"harness/ root may only contain {sorted(HARNESS_ROOT_ALLOWLIST)}; "
            f"unexpected: {unexpected}",
        )

    def test_main_and_revise_load_independently_without_reuse(self) -> None:
        for name in ("LCA-main.yaml", "LCA-revise.yaml"):
            path = WORKFLOWS / name
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertNotIn("reuse", raw)
            self.assertNotIn("stage_overrides", raw)
            self.assertNotIn("runtime_spec", raw)
            workflow = load_workflow(
                path, project_root=PROJECT_ROOT, capabilities=base_capabilities()
            )
            self.assertEqual(len(workflow.stages), 4)
            self.assertEqual(len(workflow.bundles), 7)
            self.assertEqual(
                peek_tool_ids(path, project_root=PROJECT_ROOT),
                ["control_openlca", "lca_artifacts"],
            )
            for stage in workflow.stages:
                self.assertTrue(stage.spec.endswith("spec.yaml"), stage.spec)
            for assignment in workflow.assignments.values():
                self.assertFalse(hasattr(assignment, "task_spec"))

    def test_loader_rejects_python_provider_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["registry"]["checkers"] = {
                "x": {"provider": "harness.tools.lca_artifacts.checkers:inventory"}
            }
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                load_workflow(path, project_root=root, capabilities=base_capabilities())
            self.assertIn("checkers", str(ctx.exception).lower())

    def test_generic_non_lca_harness_with_fake_stdio_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = write_fake_mcp_server(root)
            path = write_minimal_workflow(
                root,
                workflow_id="generic",
                filename="generic.yaml",
                tool_command=sys.executable,
                tool_args=[str(script)],
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            self.assertEqual(workflow.workflow_id, "generic")
            self.assertEqual(len(workflow.stages), 1)
            bundle = workflow.bundles["s1.executor"]
            self.assertEqual(bundle.tool_ids, ["probe"])
            self.assertEqual(bundle.acceptance_checks[0].call, "validate")
            self.assertEqual(
                bundle.stage_spec.source_path, "harness/specs/s1/spec.yaml"
            )
            self.assertNotIn("paths", bundle.rule_ids)
            self.assertIn("extra_rule", bundle.rule_ids)

            from core.runtime.context import RunContext

            run_ctx = RunContext(
                project_root=root,
                workspace_root=root / "workspace",
                run_id="r1",
                stage_id="s1",
                assignment_id="s1.executor",
                attempt=1,
                role="executor",
                metadata={},
            )
            (root / "workspace").mkdir(parents=True, exist_ok=True)
            with patch(
                "core.runtime.mcp_host._stdio_call",
                return_value={
                    "ok": True,
                    "status": "passed",
                    "summary": "ok",
                    "errors": [],
                    "warnings": [],
                },
            ):
                result = invoke_tool(
                    workflow.tools["probe"],
                    "validate",
                    {},
                    run_ctx=run_ctx,
                    project_root=root,
                )
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "passed")
            self.assertEqual(peek_tool_ids(path, project_root=root), ["probe"])


if __name__ == "__main__":
    unittest.main()
