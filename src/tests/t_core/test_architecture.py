"""Architecture guards: core stays harness-agnostic; harness tools stay core-free."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from core.runtime.capabilities import base_capabilities
from core.runtime.context import RunContext
from core.runtime.mcp_host import invoke_tool
from core.workflow.config.loader import load_workflow
from core.workflow.main import peek_tool_ids
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.minimal_workflow import write_fake_mcp_server, write_minimal_workflow

CORE_ROOT = PROJECT_ROOT / "src" / "core"
HARNESS_ROOT = PROJECT_ROOT / "harness"
HARNESS_TOOLS = HARNESS_ROOT / "tools"
BANNED_IMPORT_PREFIXES = (
    "domains",
    "services",
    "schema",
    "gui",
    "scripts",
    "harness",
)
HARNESS_BANNED_CORE = ("core",)
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
HARNESS_TOOLS_ALLOWLIST = frozenset({"mcp", "host_action", "shared"})


def _src_env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")}


def _root_env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _module_prefixes(node: ast.AST) -> list[str]:
    names: list[str] = []
    if isinstance(node, ast.Import):
        names.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        names.append(node.module)
    return names


def _is_banned(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".") for prefix in prefixes
    )


class CoreArchitectureTests(unittest.TestCase):
    def test_core_sources_do_not_hard_import_harness_or_app_layers(self) -> None:
        violations: list[str] = []
        for path in _iter_py_files(CORE_ROOT):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                for module in _module_prefixes(node):
                    if _is_banned(module, BANNED_IMPORT_PREFIXES):
                        rel = path.relative_to(PROJECT_ROOT)
                        violations.append(f"{rel}: import {module}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_harness_tools_do_not_import_core(self) -> None:
        violations: list[str] = []
        for path in _iter_py_files(HARNESS_TOOLS):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                for module in _module_prefixes(node):
                    if _is_banned(module, HARNESS_BANNED_CORE):
                        rel = path.relative_to(PROJECT_ROOT)
                        violations.append(f"{rel}: import {module}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_core_has_no_providers_compose_or_dead_registries(self) -> None:
        self.assertFalse((CORE_ROOT / "runtime" / "providers.py").exists())
        self.assertFalse((CORE_ROOT / "runtime" / "compose.py").exists())
        self.assertFalse((CORE_ROOT / "runtime" / "checkers.py").exists())
        self.assertFalse((CORE_ROOT / "runtime" / "hooks.py").exists())

    def test_importing_core_workflow_does_not_load_harness(self) -> None:
        code = """
import sys
from core.workflow.main import main, peek_tool_ids
from core.runtime.capabilities import base_capabilities
assert callable(main) and callable(peek_tool_ids)
caps = base_capabilities()
assert caps is not None
assert hasattr(caps, "knowledge")
assert not hasattr(caps, "checkers")
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
        tools_names = {p.name for p in (HARNESS_ROOT / "tools").iterdir() if p.is_dir()}
        unexpected_tools = sorted(tools_names - HARNESS_TOOLS_ALLOWLIST)
        self.assertEqual(
            unexpected_tools,
            [],
            f"harness/tools may only contain {sorted(HARNESS_TOOLS_ALLOWLIST)}; "
            f"unexpected: {unexpected_tools}",
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
            self.assertGreaterEqual(len(workflow.stages), 1)
            self.assertGreaterEqual(len(workflow.bundles), 1)
            self.assertTrue(peek_tool_ids(path, project_root=PROJECT_ROOT))
            for stage in workflow.stages:
                self.assertTrue(stage.spec.endswith("spec.yaml"), stage.spec)
                roles = [workflow.assignments[step].role for step in stage.steps]
                if len(roles) == 1:
                    self.assertEqual(roles, ["reviewer"], stage.stage_id)
                else:
                    self.assertEqual(len(roles), 2, stage.stage_id)
                    self.assertIn(roles[0], {"executor", "reviser"})
                    self.assertEqual(roles[1], "reviewer")
            for assignment in workflow.assignments.values():
                self.assertFalse(hasattr(assignment, "task_spec"))

    def test_loader_rejects_python_provider_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["registry"]["checkers"] = {"x": {"provider": "some.module:factory"}}
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                load_workflow(path, project_root=root, capabilities=base_capabilities())
            self.assertIn("checkers", str(ctx.exception).lower())

    def test_synthetic_two_and_n_stage_topologies_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = write_fake_mcp_server(root)
            two = write_minimal_workflow(
                root,
                workflow_id="two",
                filename="two.yaml",
                stage_id="a",
                tool_command=sys.executable,
                tool_args=[str(script)],
            )
            # Clone into a second stage for N=2 synthetic.
            payload = yaml.safe_load(two.read_text(encoding="utf-8"))
            from tests.support.minimal_workflow import write_stage_spec

            write_stage_spec(root, stage_id="b", action="verify", acceptance=[])
            payload["stages"].append(
                {
                    "id": "b",
                    "spec": "harness/specs/b/spec.yaml",
                    "steps": [
                        {"assignment": "b.executor"},
                        {"assignment": "b.reviewer"},
                    ],
                }
            )
            payload["assignments"]["b.executor"] = {
                "role": "executor",
                "tools": {"mcp": ["probe"]},
            }
            payload["assignments"]["b.reviewer"] = {
                "role": "reviewer",
                "tools": {"mcp": []},
            }
            two.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            one = write_minimal_workflow(
                root,
                workflow_id="one",
                filename="one.yaml",
                stage_id="only",
                tool_command=sys.executable,
                tool_args=[str(script)],
            )
            w1 = load_workflow(one, project_root=root, capabilities=base_capabilities())
            w2 = load_workflow(two, project_root=root, capabilities=base_capabilities())
            self.assertEqual(len(w1.stages), 1)
            self.assertEqual(len(w2.stages), 2)

    def test_generic_non_lca_harness_with_fake_stdio_mcp_mocked(self) -> None:
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
            self.assertEqual(bundle.acceptance_checks[0].action, "verify")
            self.assertEqual(
                bundle.stage_spec.source_path, "harness/specs/s1/spec.yaml"
            )
            self.assertNotIn("paths", bundle.rule_ids)
            self.assertIn("extra_rule", bundle.rule_ids)
            self.assertEqual(peek_tool_ids(path, project_root=root), ["probe"])

    def test_real_stdio_invoke_tool_without_mock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                workflow_id="stdio-smoke",
                filename="stdio-smoke.yaml",
                tool_command=sys.executable,
            )
            script = write_fake_mcp_server(root)
            # Refresh args to the rewritten fake server script.
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["registry"]["tools"]["mcp"]["probe"]["args"] = [str(script)]
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
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
            result = invoke_tool(
                workflow.tools["probe"],
                "echo",
                {},
                run_ctx=run_ctx,
                project_root=root,
            )
            self.assertTrue(result.ok, result.summary)
            self.assertEqual(result.status, "passed")

    def test_harness_mcp_entrypoints_start_with_root_pythonpath(self) -> None:
        for relative in (
            "harness/tools/mcp/lca_artifacts/main.py",
            "harness/tools/mcp/control_openlca/workflow_mcp.py",
            "harness/tools/host_action/lca_artifacts/main.py",
        ):
            code = (
                "import ast, pathlib, sys\n"
                f"path = pathlib.Path({relative!r})\n"
                "tree = ast.parse(path.read_text(encoding='utf-8'))\n"
                "for node in ast.walk(tree):\n"
                "    if isinstance(node, (ast.Import, ast.ImportFrom)):\n"
                "        mods = []\n"
                "        if isinstance(node, ast.Import):\n"
                "            mods = [a.name for a in node.names]\n"
                "        elif node.module:\n"
                "            mods = [node.module]\n"
                "        for mod in mods:\n"
                "            if mod == 'core' or mod.startswith('core.'):\n"
                "                raise SystemExit(f'core import in {path}: {mod}')\n"
                "print('ok')\n"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=PROJECT_ROOT,
                env=_root_env(),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
