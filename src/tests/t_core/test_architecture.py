"""Architecture guards: core stays harness-agnostic; CLI takes --workflow only."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests.conftest import PROJECT_ROOT

CORE_ROOT = PROJECT_ROOT / "src" / "core"
BANNED_IMPORT_PREFIXES = (
    "domains",
    "services",
    "schema",
    "gui",
    "scripts",
    "harness.tools",
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

    def test_importing_core_workflow_does_not_load_harness_tools(self) -> None:
        code = """
import sys
from core.workflow.main import main, peek_capability_ids
from core.runtime.compose import compose_capabilities_from_providers
assert callable(main) and callable(peek_capability_ids)
compose_capabilities_from_providers(
    checkers={}, hooks={}, handoff_validators={}
)
banned = ("domains", "services", "schema", "harness.tools", "gui", "scripts")
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
        self.assertFalse((PROJECT_ROOT / "harness" / "index.yaml").exists())


if __name__ == "__main__":
    unittest.main()
