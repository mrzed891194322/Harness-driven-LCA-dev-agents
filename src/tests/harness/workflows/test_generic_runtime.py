from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from harness.domains.lca.bootstrap import lca_capabilities
from harness.runtime.capabilities import HarnessCapabilities
from harness.runtime.checkers import CheckerRegistry
from harness.runtime.context import RunContext
from harness.runtime.hooks import HookRegistry
from harness.runtime.knowledge import KnowledgeProviderRegistry
from lca_orchestrator.loader import load_workflow
from lca_orchestrator.session_bind import build_session_config
from tests.conftest import PROJECT_ROOT, WORKFLOWS


def _test_capabilities() -> HarnessCapabilities:
    checkers = CheckerRegistry()
    knowledge = KnowledgeProviderRegistry()
    hooks = HookRegistry()

    def ping_validate(ctx: RunContext) -> dict[str, Any]:
        return {"ok": True, "errors": [], "summary": "ok"}

    def ping_state(ctx: RunContext) -> dict[str, Any]:
        return {"check_id": "test.ping", "status": "not_run"}

    checkers.register(
        "test.ping",
        validation_state=ping_state,
        run_validate=ping_validate,
    )
    knowledge.register(
        "test.sources",
        lambda ctx, bundle: {
            "source_manifest": {"path": "memory/test/sources.json", "sha256": "0"}
        },
    )
    hooks.register("test.noop", lambda _ctx: None)
    return HarnessCapabilities(checkers=checkers, knowledge=knowledge, hooks=hooks)


class GenericRuntimeTests(unittest.TestCase):
    def test_fake_workflow_without_lca_stage_ids(self) -> None:
        caps = _test_capabilities()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = _write_fake_workflow(root)
            workflow = load_workflow(path, project_root=root, capabilities=caps)
            bundle = workflow.bundles["alpha.executor"]
            self.assertEqual(bundle.stage_id, "alpha-step")
            self.assertEqual(bundle.checks[0].checker_id, "test.ping")

    def test_renamed_stage_runs_lca_inventory_checker(self) -> None:
        from harness.tools.lca_artifacts import checks as lca_checks

        caps = lca_capabilities()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = _write_renamed_inventory_workflow(root)
            load_workflow(path, project_root=root, capabilities=caps)
            ctx = RunContext(
                project_root=root,
                workspace_root=root / "workspace",
                run_id="r1",
                stage_id="inv-phase",
                assignment_id="inv-phase.executor",
                attempt=1,
                role="executor",
                metadata={"lca": {"phase": "inventory"}},
            )
            (ctx.workspace_root / "inputs").mkdir(parents=True)
            (ctx.workspace_root / "inputs" / "plan.md").write_text(
                "# plan\n", encoding="utf-8"
            )
            with patch.object(lca_checks, "inventory_errors", return_value=[]):
                result = caps.checkers.run_validate(ctx, "lca.inventory")
            self.assertTrue(result.get("ok"))

    def test_tool_runtime_without_whitelist(self) -> None:
        caps = _test_capabilities()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = _write_tool_runtime_workflow(root)
            workflow = load_workflow(path, project_root=root, capabilities=caps)
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
                run_id="run-1",
                attempt=1,
            )
            server = config.mcp_servers["fake_tool"]
            self.assertIn("HARNESS_RUN_ID", server["env"])
            self.assertIn("--context-file", server["args"])
            plain = config.mcp_servers["plain_tool"]
            self.assertNotIn("HARNESS_RUN_ID", plain.get("env", {}))

    def test_unknown_checker_fail_fast(self) -> None:
        caps = _test_capabilities()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = _write_fake_workflow(root)
            text = yaml.safe_load(path.read_text(encoding="utf-8"))
            text["stages"][0]["checks"] = [{"id": "missing.checker"}]
            path.write_text(yaml.safe_dump(text, allow_unicode=True), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=caps)

    def test_lca_main_hooks_on_bundle(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        inventory = workflow.bundles["02-inventory-extraction.reviewer"]
        mapping = workflow.bundles["03-dataset-mapping.reviewer"]
        report = workflow.bundles["04-openlca-reporting.reviewer"]
        self.assertNotIn("lca.record_acceptance", inventory.reviewer_passed_hooks)
        self.assertIn("lca.record_acceptance", mapping.reviewer_passed_hooks)
        self.assertNotIn("lca.record_acceptance", report.reviewer_passed_hooks)


def _write_fake_workflow(root: Path) -> Path:
    _write_minimal_files(root)
    workflows = root / "harness" / "workflows"
    payload = {
        "id": "fake",
        "runtime_spec": "harness/specs/public/references/workflow-runtime-spec.md",
        "hooks": {"on_reviewer_passed": ["test.noop"]},
        "registry": {
            "rules": {
                "workspace_boundary": "harness/rules/project/write-boundary.md",
                "runtime": "harness/rules/project/runtime.md",
                "paths": "harness/rules/project/paths.md",
            },
            "tools": {
                "noop_tool": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["harness/tools/lca_artifacts/main.py"],
                }
            },
            "knowledge": {
                "k1": {
                    "kind": "local_dir",
                    "path": "harness/knowledge/",
                    "provider": "test.sources",
                }
            },
        },
        "defaults": {
            "rules": ["workspace_boundary", "runtime", "paths"],
            "knowledge": ["k1"],
        },
        "stages": [
            {
                "id": "alpha-step",
                "spec": "harness/specs/s1/README.md",
                "checks": [{"id": "test.ping"}],
                "steps": [
                    {"assignment": "alpha.executor"},
                    {"assignment": "alpha.reviewer"},
                ],
            }
        ],
        "assignments": {
            "alpha.executor": {
                "role": "executor",
                "task_spec": "harness/specs/s1/executor.md",
                "tools": [],
            },
            "alpha.reviewer": {
                "role": "reviewer",
                "task_spec": "harness/specs/s1/reviewer.md",
                "tools": [],
            },
        },
    }
    path = workflows / "fake.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def _write_renamed_inventory_workflow(root: Path) -> Path:
    _write_minimal_files(root)
    workflows = root / "harness" / "workflows"
    payload = {
        "id": "renamed-inv",
        "runtime_spec": "harness/specs/public/references/workflow-runtime-spec.md",
        "registry": {
            "rules": {
                "workspace_boundary": "harness/rules/project/write-boundary.md",
                "runtime": "harness/rules/project/runtime.md",
                "paths": "harness/rules/project/paths.md",
            },
            "tools": {},
            "knowledge": {
                "k1": {
                    "kind": "local_dir",
                    "path": "harness/knowledge/",
                    "provider": "local_files",
                }
            },
        },
        "defaults": {
            "rules": ["workspace_boundary", "runtime", "paths"],
            "knowledge": ["k1"],
        },
        "stages": [
            {
                "id": "inv-phase",
                "spec": "harness/specs/s1/README.md",
                "context": {"lca": {"phase": "inventory"}},
                "checks": [{"id": "lca.inventory"}],
                "steps": [
                    {"assignment": "inv-phase.executor"},
                    {"assignment": "inv-phase.reviewer"},
                ],
            }
        ],
        "assignments": {
            "inv-phase.executor": {
                "role": "executor",
                "task_spec": "harness/specs/s1/executor.md",
                "tools": [],
            },
            "inv-phase.reviewer": {
                "role": "reviewer",
                "task_spec": "harness/specs/s1/reviewer.md",
                "tools": [],
            },
        },
    }
    path = workflows / "renamed.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def _write_tool_runtime_workflow(root: Path) -> Path:
    _write_minimal_files(root)
    workflows = root / "harness" / "workflows"
    payload = {
        "id": "tools",
        "runtime_spec": "harness/specs/public/references/workflow-runtime-spec.md",
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
                    "args": ["harness/tools/lca_artifacts/main.py"],
                    "runtime": {
                        "run_context_env": True,
                        "context_file": True,
                    },
                },
                "plain_tool": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["harness/tools/lca_artifacts/main.py"],
                },
            },
            "knowledge": {},
        },
        "defaults": {"rules": ["workspace_boundary", "runtime", "paths"]},
        "stages": [
            {
                "id": "s1",
                "spec": "harness/specs/s1/README.md",
                "steps": [
                    {"assignment": "s1.executor"},
                    {"assignment": "s1.reviewer"},
                ],
            }
        ],
        "assignments": {
            "s1.executor": {
                "role": "executor",
                "task_spec": "harness/specs/s1/executor.md",
                "tools": ["fake_tool", "plain_tool"],
            },
            "s1.reviewer": {
                "role": "reviewer",
                "task_spec": "harness/specs/s1/reviewer.md",
                "tools": [],
            },
        },
    }
    path = workflows / "tools.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def _write_minimal_files(root: Path) -> None:
    specs = root / "harness" / "specs" / "s1"
    specs.mkdir(parents=True)
    (specs / "README.md").write_text("# stage\n", encoding="utf-8")
    (specs / "executor.md").write_text("role=executor\n", encoding="utf-8")
    (specs / "reviewer.md").write_text("role=reviewer\n", encoding="utf-8")
    rules = root / "harness" / "rules" / "project"
    rules.mkdir(parents=True)
    for name in ("write-boundary.md", "runtime.md", "paths.md"):
        (rules / name).write_text(f"# {name}\n", encoding="utf-8")
    runtime = root / "harness" / "specs" / "public" / "references"
    runtime.mkdir(parents=True)
    (runtime / "workflow-runtime-spec.md").write_text("# runtime\n", encoding="utf-8")
    tools = root / "harness" / "tools" / "lca_artifacts"
    tools.mkdir(parents=True)
    (tools / "main.py").write_text("print('ok')\n", encoding="utf-8")
    knowledge = root / "harness" / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "README.md").write_text("# k\n", encoding="utf-8")
    (root / "harness" / "workflows").mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    unittest.main()
