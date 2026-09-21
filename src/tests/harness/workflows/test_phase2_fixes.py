"""Regression coverage for phase-1/2 leftover fixes."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from harness.domains.lca.bootstrap import lca_capabilities
from harness.domains.lca.knowledge import enrich_local_files
from harness.runtime.capabilities import empty_capabilities
from harness.runtime.context import RunContext
from harness.tools.lca_artifacts import checks as lca_checks
from harness.tools.lca_artifacts.store import Context
from harness.workflows.lca_orchestrator.bundle import KnowledgeBinding, TaskBundle
from harness.workflows.lca_orchestrator.lists import resolve_list
from harness.workflows.lca_orchestrator.loader import load_workflow
from tests.conftest import PROJECT_ROOT, WORKFLOWS


def _minimal_tree(root: Path) -> None:
    specs = root / "harness" / "specs" / "s1"
    specs.mkdir(parents=True)
    (specs / "README.md").write_text("# stage\n", encoding="utf-8")
    (specs / "executor.md").write_text("role=executor\n", encoding="utf-8")
    (specs / "reviewer.md").write_text("role=reviewer\n", encoding="utf-8")
    rules = root / "harness" / "rules" / "project"
    rules.mkdir(parents=True)
    for name in ("write-boundary.md", "runtime.md", "paths.md", "extra.md", "other.md"):
        (rules / name).write_text(f"# {name}\n", encoding="utf-8")
    runtime = root / "harness" / "specs" / "public" / "references"
    runtime.mkdir(parents=True)
    (runtime / "workflow-runtime-spec.md").write_text("# runtime\n", encoding="utf-8")
    tools = root / "harness" / "tools" / "lca_artifacts"
    tools.mkdir(parents=True)
    (tools / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "harness" / "workflows").mkdir(parents=True)
    (root / "harness" / "knowledge").mkdir(parents=True)
    (root / "custom_docs").mkdir(parents=True)


def _base_payload() -> dict:
    return {
        "id": "phase2",
        "runtime_spec": "harness/specs/public/references/workflow-runtime-spec.md",
        "registry": {
            "rules": {
                "workspace_boundary": "harness/rules/project/write-boundary.md",
                "runtime": "harness/rules/project/runtime.md",
                "paths": "harness/rules/project/paths.md",
                "extra_rule": "harness/rules/project/extra.md",
                "other_rule": "harness/rules/project/other.md",
            },
            "tools": {
                "lca_artifacts": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["harness/tools/lca_artifacts/main.py"],
                }
            },
            "knowledge": {
                "workspace_knowledge": {
                    "kind": "local_dir",
                    "path": "harness/knowledge/",
                    "provider": "local_files",
                },
                "custom_docs": {
                    "kind": "local_dir",
                    "path": "custom_docs/",
                    "provider": "local_files",
                },
            },
        },
        "defaults": {
            "rules": ["workspace_boundary", "runtime", "paths"],
            "knowledge": ["workspace_knowledge"],
        },
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
                "tools": ["lca_artifacts"],
            },
            "s1.reviewer": {
                "role": "reviewer",
                "task_spec": "harness/specs/s1/reviewer.md",
                "tools": [],
            },
        },
    }


class ListInheritTests(unittest.TestCase):
    def test_defaults_to_assignment_remove_add(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            payload = _base_payload()
            payload["assignments"]["s1.executor"]["rules"] = {
                "add": ["extra_rule"],
                "remove": ["paths"],
            }
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            rules = workflow.bundles["s1.executor"].rule_ids
            self.assertIn("extra_rule", rules)
            self.assertNotIn("paths", rules)
            self.assertIn("workspace_boundary", rules)

    def test_stage_then_assignment_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            payload = _base_payload()
            payload["stages"][0]["rules"] = {"add": ["extra_rule"], "remove": ["paths"]}
            payload["assignments"]["s1.executor"]["rules"] = {
                "add": ["other_rule"],
                "remove": ["runtime"],
            }
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            rules = workflow.bundles["s1.executor"].rule_ids
            self.assertEqual(
                rules,
                ["workspace_boundary", "extra_rule", "other_rule"],
            )

    def test_empty_list_clears_inherited(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            payload = _base_payload()
            payload["assignments"]["s1.executor"]["knowledge"] = []
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            self.assertEqual(workflow.bundles["s1.executor"].knowledge_ids, [])

    def test_plain_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            payload = _base_payload()
            payload["assignments"]["s1.executor"]["rules"] = ["extra_rule"]
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            self.assertEqual(workflow.bundles["s1.executor"].rule_ids, ["extra_rule"])

    def test_reuse_overlay_add_remove(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            base = _base_payload()
            base_path = root / "harness" / "workflows" / "base.yaml"
            base_path.write_text(
                yaml.safe_dump(base, allow_unicode=True), encoding="utf-8"
            )
            overlay = {
                "id": "overlay",
                "reuse": "harness/workflows/base.yaml",
                "assignments": {
                    "s1.executor": {
                        "role": "executor",
                        "task_spec": "harness/specs/s1/executor.md",
                        "tools": ["lca_artifacts"],
                        "rules": {"add": ["extra_rule"], "remove": ["paths"]},
                        "knowledge": {
                            "add": ["custom_docs"],
                            "remove": ["workspace_knowledge"],
                        },
                    }
                },
            }
            path = root / "harness" / "workflows" / "overlay.yaml"
            path.write_text(
                yaml.safe_dump(overlay, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            bundle = workflow.bundles["s1.executor"]
            self.assertIn("extra_rule", bundle.rule_ids)
            self.assertNotIn("paths", bundle.rule_ids)
            self.assertEqual(bundle.knowledge_ids, ["custom_docs"])

    def test_resolve_list_unit(self) -> None:
        self.assertEqual(resolve_list(["a", "b"], None), ["a", "b"])
        self.assertEqual(resolve_list(["a", "b"], []), [])
        self.assertEqual(resolve_list(["a", "b"], ["c"]), ["c"])
        self.assertEqual(
            resolve_list(["a", "b", "c"], {"remove": ["b"], "add": ["d"]}),
            ["a", "c", "d"],
        )

    def test_revise_keeps_role_rules(self) -> None:
        revise = load_workflow(
            WORKFLOWS / "LCA-revise.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        reviser = revise.bundles["03-dataset-mapping.reviser"]
        reviewer = revise.bundles["03-dataset-mapping.reviewer"]
        self.assertIn("reviewer_readonly", reviewer.rule_ids)
        self.assertIn("knowledge_files", reviser.rule_ids)
        self.assertIn("lca_method", reviser.rule_ids)
        self.assertIn("user_intent", reviser.rule_ids)
        self.assertIn("user_intent", reviewer.rule_ids)
        self.assertIn("lca.record_acceptance", reviewer.reviewer_passed_hooks)


class AcceptancePhaseTests(unittest.TestCase):
    def test_renamed_chain_acceptance_key_and_report_phase(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "inputs").mkdir()
            (workspace / "inputs" / "plan.md").write_text("# plan\n", encoding="utf-8")
            map_ctx = Context(
                root,
                workspace,
                "run-a",
                "map-phase",
                1,
                "reviewer",
                "map-phase.reviewer",
                {"lca": {"phase": "mapping"}},
            )
            map_ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            map_ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-a", "calls": []}),
                encoding="utf-8",
            )
            inputs = lca_checks.dependencies(map_ctx, "mapping")
            check_path = lca_checks.check_path(map_ctx, "mapping")
            check_path.parent.mkdir(parents=True, exist_ok=True)
            check_path.write_text(
                json.dumps(
                    {
                        "check_id": "mapping",
                        "checker_version": lca_checks.CHECKER_VERSION,
                        "status": "passed",
                        "inputs": inputs,
                        "executed_at": "2020-01-01T00:00:00Z",
                        "summary": "ok",
                        "errors": [],
                        "warnings": [],
                    }
                ),
                encoding="utf-8",
            )
            lca_checks.record_acceptance(map_ctx)
            accepted = map_ctx.load_manifest()["accepted"][lca_checks.ACCEPTANCE_MODEL]
            self.assertEqual(accepted["stage"], "map-phase")
            self.assertEqual(accepted["inputs"]["files"], inputs["files"])

            report = Context(
                root,
                workspace,
                "run-a",
                "rpt-phase",
                1,
                "executor",
                "rpt-phase.executor",
                {"lca": {"phase": "report"}},
            )
            # Should pass when fingerprint matches and phase is report.
            lca_checks.require_approved_model(report)

            mapping_writer = Context(
                root,
                workspace,
                "run-a",
                "map-phase",
                1,
                "executor",
                "map-phase.executor",
                {"lca": {"phase": "mapping"}},
            )
            with self.assertRaises(ValueError):
                lca_checks.require_approved_model(mapping_writer)

    def test_profiles_are_not_stage_ids(self) -> None:
        for name in lca_checks.INTERNAL_PROFILES:
            self.assertFalse(name.startswith("0"))
            self.assertEqual(lca_checks.PROFILES[name], name)


class KnowledgeFingerprintTests(unittest.TestCase):
    def test_bound_custom_docs_affects_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "inputs").mkdir()
            (workspace / "inputs" / "plan.md").write_text("# plan\n", encoding="utf-8")
            custom = root / "custom_docs" / "a.txt"
            custom.write_text("v1\n", encoding="utf-8")
            (root / "harness" / "knowledge" / "ignored.txt").write_text(
                "noise\n", encoding="utf-8"
            )
            ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="r1",
                stage_id="s1",
                assignment_id="s1.executor",
                attempt=1,
                role="executor",
            )
            bundle = TaskBundle(
                workflow_id="phase2",
                stage_id="s1",
                assignment_id="s1.executor",
                role="executor",
                max_attempts=1,
                runtime_spec="harness/specs/public/references/workflow-runtime-spec.md",
                knowledge_sources=[
                    KnowledgeBinding(
                        knowledge_id="custom_docs",
                        kind="local_dir",
                        path="custom_docs/",
                        provider="local_files",
                    )
                ],
            )
            enrich_local_files(ctx, bundle)
            lca_ctx = Context(
                root,
                workspace,
                "r1",
                "s1",
                1,
                "executor",
                "s1.executor",
                {},
            )
            fp1 = lca_checks.model_fingerprint(lca_ctx)
            custom.write_text("v2\n", encoding="utf-8")
            enrich_local_files(ctx, bundle)
            fp2 = lca_checks.model_fingerprint(lca_ctx)
            self.assertNotEqual(fp1, fp2)
            (root / "harness" / "knowledge" / "ignored.txt").write_text(
                "changed\n", encoding="utf-8"
            )
            fp3 = lca_checks.model_fingerprint(lca_ctx)
            self.assertEqual(fp2, fp3)

    def test_assignment_scoped_source_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            (root / "custom_docs" / "a.txt").write_text("a\n", encoding="utf-8")
            (root / "harness" / "knowledge" / "b.txt").write_text(
                "b\n", encoding="utf-8"
            )
            run_id = "r2"
            for assignment_id, knowledge_path, kid in (
                ("a.executor", "custom_docs/", "custom_docs"),
                ("b.executor", "harness/knowledge/", "workspace_knowledge"),
            ):
                ctx = RunContext(
                    project_root=root,
                    workspace_root=workspace,
                    run_id=run_id,
                    stage_id="s1",
                    assignment_id=assignment_id,
                    attempt=1,
                    role="executor",
                )
                bundle = TaskBundle(
                    workflow_id="phase2",
                    stage_id="s1",
                    assignment_id=assignment_id,
                    role="executor",
                    max_attempts=1,
                    runtime_spec="harness/specs/public/references/workflow-runtime-spec.md",
                    knowledge_sources=[
                        KnowledgeBinding(
                            knowledge_id=kid,
                            kind="local_dir",
                            path=knowledge_path,
                            provider="local_files",
                        )
                    ],
                )
                enrich_local_files(ctx, bundle)
            a_path = (
                workspace
                / "memory"
                / "evidence"
                / run_id
                / "sources"
                / "a.executor.json"
            )
            b_path = (
                workspace
                / "memory"
                / "evidence"
                / run_id
                / "sources"
                / "b.executor.json"
            )
            self.assertTrue(a_path.is_file())
            self.assertTrue(b_path.is_file())
            a_files = {f["path"] for f in json.loads(a_path.read_text())["files"]}
            b_files = {f["path"] for f in json.loads(b_path.read_text())["files"]}
            self.assertTrue(any(p.startswith("custom_docs/") for p in a_files))
            self.assertFalse(any(p.startswith("harness/knowledge/") for p in a_files))
            self.assertTrue(any(p.startswith("harness/knowledge/") for p in b_files))


class RuntimeBoundaryTests(unittest.TestCase):
    def test_run_context_has_no_lca_phase_field(self) -> None:
        from dataclasses import fields

        from harness.runtime.context import RunContext

        names = {f.name for f in fields(RunContext)}
        self.assertNotIn("lca_phase", names)
        self.assertIn("metadata", names)

    def test_runtime_does_not_import_lca_domain(self) -> None:
        banned = [
            name
            for name in list(sys.modules)
            if name == "harness.domains.lca" or name.startswith("harness.domains.lca.")
        ]
        for name in banned:
            sys.modules.pop(name, None)
        sys.modules.pop("harness.runtime", None)
        sys.modules.pop("harness.runtime.capabilities", None)
        runtime = importlib.import_module("harness.runtime")
        self.assertNotIn("harness.domains.lca", sys.modules)
        self.assertFalse(
            any(name.startswith("harness.domains.lca.") for name in sys.modules)
        )
        caps = runtime.empty_capabilities()
        self.assertEqual(set(caps.checkers.known_ids()), set())

    def test_fake_workflow_loads_without_lca_registry(self) -> None:
        caps = empty_capabilities()
        from harness.runtime.checkers import CheckerRegistry
        from harness.runtime.hooks import HookRegistry
        from harness.runtime.knowledge import KnowledgeProviderRegistry

        checkers = CheckerRegistry()
        hooks = HookRegistry()
        knowledge = KnowledgeProviderRegistry()

        def _ok(_ctx: RunContext) -> dict:
            return {"ok": True, "errors": [], "summary": "ok"}

        checkers.register("test.ping", validation_state=lambda c: {}, run_validate=_ok)
        hooks.register("test.noop", lambda _c: None)
        knowledge.register("test.sources", lambda c, b: {})
        caps = type(caps)(checkers=checkers, knowledge=knowledge, hooks=hooks)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            payload = _base_payload()
            payload["hooks"] = {"on_reviewer_passed": ["test.noop"]}
            payload["registry"]["knowledge"] = {}
            payload["defaults"]["knowledge"] = []
            payload["stages"][0]["checks"] = [{"id": "test.ping"}]
            path = root / "harness" / "workflows" / "fake.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(path, project_root=root, capabilities=caps)
            self.assertEqual(
                workflow.bundles["s1.executor"].checks[0].checker_id, "test.ping"
            )


class FailFastSessionCliTests(unittest.TestCase):
    def test_unknown_top_level_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            payload = _base_payload()
            payload["mystery"] = True
            path = root / "harness" / "workflows" / "bad.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_unknown_stage_override_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _minimal_tree(root)
            base = _base_payload()
            base_path = root / "harness" / "workflows" / "base.yaml"
            base_path.write_text(
                yaml.safe_dump(base, allow_unicode=True), encoding="utf-8"
            )
            overlay = {
                "id": "bad-overlay",
                "reuse": "harness/workflows/base.yaml",
                "stage_overrides": {"missing-stage": {"max_attempts": 1}},
            }
            path = root / "harness" / "workflows" / "overlay.yaml"
            path.write_text(
                yaml.safe_dump(overlay, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "unknown stage"):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_session_key_is_assignment_id(self) -> None:
        from harness.workflows.lca_orchestrator.graph import session_key

        self.assertEqual(
            session_key("03-dataset-mapping.executor"), "03-dataset-mapping.executor"
        )

    def test_workflow_cli_flag(self) -> None:
        from harness.workflows.lca_orchestrator import main as orch_main

        with (
            patch.object(orch_main, "load_workflow") as load_mock,
            patch.object(orch_main, "build_graph") as build_mock,
            patch.object(orch_main, "open_checkpointer") as cp_mock,
            patch.object(orch_main, "default_client"),
            patch.object(orch_main, "write_manifest"),
            patch.object(orch_main, "ensure_uv_cache_dir"),
            patch.object(orch_main, "set_progress_log"),
            patch.object(orch_main, "print_orchestrator"),
        ):
            load_mock.return_value = load_workflow(
                WORKFLOWS / "LCA-main.yaml",
                project_root=PROJECT_ROOT,
                capabilities=lca_capabilities(),
            )

            class _Conn:
                def close(self) -> None:
                    return None

            cp_mock.return_value = (_Conn(), object())

            class _Compiled:
                def invoke(self, *_a, **_k):
                    return {"status": "completed"}

            class _Graph:
                def compile(self, checkpointer=None):
                    return _Compiled()

            build_mock.return_value = _Graph()
            with tempfile.TemporaryDirectory() as temp_dir:
                workspace = Path(temp_dir)
                code = orch_main.main(
                    [
                        "--workflow",
                        str(WORKFLOWS / "LCA-main.yaml"),
                        "--project-root",
                        str(PROJECT_ROOT),
                        "--workspace",
                        str(workspace),
                        "--worker",
                        "codex",
                    ]
                )
            self.assertEqual(code, 0)
            load_mock.assert_called()
            called_path = load_mock.call_args.args[0]
            self.assertTrue(str(called_path).endswith("LCA-main.yaml"))


class KnowledgeDocsTests(unittest.TestCase):
    def test_agent_rules_do_not_mandate_harness_knowledge_path(self) -> None:
        text = (PROJECT_ROOT / "harness/rules/lca/knowledge-files.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("source_manifest", text)
        self.assertNotIn("默认目录 `harness/knowledge/`", text)
        for relative in (
            "harness/specs/01-intake-gate/README.md",
            "harness/specs/01-intake-gate/reviewer.md",
            "harness/specs/02-inventory-extraction/README.md",
            "harness/specs/02-inventory-extraction/executor.md",
        ):
            body = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn(
                "必须读取 `harness/knowledge/`",
                body,
                relative,
            )


if __name__ == "__main__":
    unittest.main()
