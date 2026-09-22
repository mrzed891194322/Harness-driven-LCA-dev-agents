"""Merge-ready closeout: reviewer guard, acceptance/evidence, path/caps/v3/seq."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from harness.domains.lca.bootstrap import lca_capabilities
from harness.runtime.capabilities import base_capabilities
from harness.runtime.context import RunContext
from harness.runtime.hashing import stable_hash
from harness.runtime.identifiers import require_identifier, resolve_project_path
from harness.runtime.knowledge_providers.local_files import enrich_local_files
from harness.tools.lca_artifacts import checks as lca_checks
from harness.tools.lca_artifacts.store import Context
from harness.workflows.lca_orchestrator.bundle import KnowledgeBinding, TaskBundle
from harness.workflows.lca_orchestrator.config_fingerprint import (
    assert_runtime_config_matches,
    write_runtime_config,
)
from harness.workflows.lca_orchestrator.graph import (
    OrchestratorRuntime,
    WorkflowState,
    initial_state,
)
from harness.workflows.lca_orchestrator.lists import (
    merge_list_declarations,
    parse_optional_list_field,
    resolve_list,
)
from harness.workflows.lca_orchestrator.loader import load_workflow
from harness.workflows.lca_orchestrator.main import (
    _capabilities_for,
    compose_capabilities,
    peek_capability_ids,
)
from tests.conftest import PROJECT_ROOT, WORKFLOWS


def _tree(root: Path) -> None:
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
    (root / "harness" / "workflows").mkdir(parents=True)
    (root / "harness" / "knowledge").mkdir(parents=True)
    (root / "custom_docs").mkdir(parents=True)
    (root / "custom_docs" / "a.txt").write_text("v1\n", encoding="utf-8")


def _stage_payload(*, with_check: bool = True, with_outputs: bool = True) -> dict:
    stage: dict = {
        "id": "s1",
        "spec": "harness/specs/s1/README.md",
        "context": {"lca": {"phase": "mapping"}},
        "steps": [
            {"assignment": "s1.executor"},
            {"assignment": "s1.reviewer"},
        ],
        "max_attempts": 3,
    }
    if with_outputs:
        stage["outputs"] = [
            "workspace/outputs/inventory/process-mapping.json",
            "workspace/outputs/LCI/",
        ]
    if with_check:
        stage["checks"] = [{"id": "lca.mapping"}]
        stage["hooks"] = {"on_reviewer_passed": ["lca.record_acceptance"]}
    return {
        "id": "merge-closeout",
        "capabilities": ["lca"],
        "runtime_spec": "harness/specs/public/references/workflow-runtime-spec.md",
        "registry": {
            "rules": {
                "workspace_boundary": "harness/rules/project/write-boundary.md",
                "runtime": "harness/rules/project/runtime.md",
                "paths": "harness/rules/project/paths.md",
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
        "stages": [stage],
        "assignments": {
            "s1.executor": {
                "role": "executor",
                "task_spec": "harness/specs/s1/executor.md",
                "tools": ["lca_artifacts"],
                "knowledge": {"add": ["custom_docs"]},
            },
            "s1.reviewer": {
                "role": "reviewer",
                "task_spec": "harness/specs/s1/reviewer.md",
                "tools": [],
            },
        },
    }


def _write_passed_check(ctx: Context, profile: str = "mapping") -> dict:
    inputs = lca_checks.dependencies(ctx, profile)
    path = lca_checks.check_path(ctx, profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "check_id": profile,
        "checker_version": lca_checks.CHECKER_VERSION,
        "status": "passed",
        "inputs": inputs,
        "executed_at": "2020-01-01T00:00:00Z",
        "summary": f"{profile}: 0 issue(s)",
        "errors": [],
        "warnings": [],
        "stage": ctx.stage,
        "assignment": ctx.assignment,
        "attempt": ctx.attempt,
    }
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def _seed_mapping_artifacts(workspace: Path) -> None:
    inv = workspace / "outputs" / "inventory"
    inv.mkdir(parents=True)
    (workspace / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace / "inputs" / "plan.md").write_text("# plan\n", encoding="utf-8")
    bom = {
        "items": [
            {
                "item_id": "one",
                "name": "物料",
                "quantity": 1,
                "unit": "kg",
                "process": "制造",
                "transport": None,
                "geography": "CN",
                "source_locations": ["custom_docs/a.txt#L1"],
                "extraction_status": "extracted",
            }
        ]
    }
    (inv / "extracted-bom.json").write_text(json.dumps(bom), encoding="utf-8")
    (inv / "process-mapping.json").write_text(
        json.dumps({"items": [{"item_id": "one", "selection_reason": "ok"}]}),
        encoding="utf-8",
    )
    lci = workspace / "outputs" / "LCI" / "flows"
    lci.mkdir(parents=True)
    (lci / "f.json").write_text(json.dumps({"@id": "f"}), encoding="utf-8")


class ReviewerPassGuardTests(unittest.TestCase):
    def _runtime(self, root: Path, workspace: Path):
        path = root / "harness" / "workflows" / "t.yaml"
        path.write_text(
            yaml.safe_dump(_stage_payload(), allow_unicode=True), encoding="utf-8"
        )
        workflow = load_workflow(
            path, project_root=root, capabilities=lca_capabilities()
        )
        hooks = MagicMock()
        caps = lca_capabilities()
        caps.hooks = hooks
        runtime = OrchestratorRuntime(
            workflow,
            project_root=root,
            workspace_root=workspace,
            session_client=MagicMock(),
            worker="codex",
            model="test-model",
            capabilities=caps,
        )
        return runtime, workflow, hooks

    def _state(self, workflow) -> WorkflowState:
        state = initial_state(
            run_id="run-guard", task="t", worker="codex", workflow=workflow
        )
        state["stage_index"] = 0
        state["step_index"] = 1
        state["attempt"] = 1
        state["current_assignment"] = "s1.reviewer"
        state["current_role"] = "reviewer"
        return state

    def test_mutated_artifact_returns_writer_without_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_artifacts(workspace)
            runtime, workflow, hooks = self._runtime(root, workspace)
            stage = workflow.stages[0]
            assignment = workflow.assignments["s1.reviewer"]
            ctx = Context(
                root,
                workspace,
                "run-guard",
                stage.stage_id,
                1,
                "reviewer",
                assignment.assignment_id,
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-guard", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            (workspace / "outputs" / "inventory" / "process-mapping.json").write_text(
                json.dumps(
                    {"items": [{"item_id": "one", "selection_reason": "changed"}]}
                ),
                encoding="utf-8",
            )
            update = runtime._advance_after_reviewer(
                self._state(workflow),
                stage,
                assignment,
                {"status": "passed", "status_reason": "ok"},
            )
            self.assertEqual(update["step_index"], 0)
            self.assertEqual(update["attempt"], 2)
            self.assertIn(
                "审查期间产物或确定性检查状态已变化", update["fix_instructions"]
            )
            hooks.run.assert_not_called()

    def test_missing_output_returns_writer_without_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_artifacts(workspace)
            runtime, workflow, hooks = self._runtime(root, workspace)
            stage = workflow.stages[0]
            assignment = workflow.assignments["s1.reviewer"]
            ctx = Context(
                root,
                workspace,
                "run-guard",
                stage.stage_id,
                1,
                "reviewer",
                assignment.assignment_id,
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-guard", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            (workspace / "outputs" / "inventory" / "process-mapping.json").unlink()
            update = runtime._advance_after_reviewer(
                self._state(workflow),
                stage,
                assignment,
                {"status": "passed", "status_reason": "ok"},
            )
            self.assertEqual(update["step_index"], 0)
            hooks.run.assert_not_called()
            self.assertIn("缺少产物", update["fix_instructions"])

    def test_stale_check_skips_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_artifacts(workspace)
            runtime, workflow, hooks = self._runtime(root, workspace)
            stage = workflow.stages[0]
            assignment = workflow.assignments["s1.reviewer"]
            ctx = Context(
                root,
                workspace,
                "run-guard",
                stage.stage_id,
                1,
                "reviewer",
                assignment.assignment_id,
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-guard", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            (workspace / "inputs" / "plan.md").write_text(
                "# changed\n", encoding="utf-8"
            )
            update = runtime._advance_after_reviewer(
                self._state(workflow),
                stage,
                assignment,
                {"status": "passed", "status_reason": "ok"},
            )
            self.assertEqual(update["step_index"], 0)
            hooks.run.assert_not_called()
            self.assertIn("stale", update["fix_instructions"])

    def test_unchanged_advances_and_runs_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_artifacts(workspace)
            runtime, workflow, hooks = self._runtime(root, workspace)
            stage = workflow.stages[0]
            assignment = workflow.assignments["s1.reviewer"]
            ctx = Context(
                root,
                workspace,
                "run-guard",
                stage.stage_id,
                1,
                "reviewer",
                assignment.assignment_id,
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-guard", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            update = runtime._advance_after_reviewer(
                self._state(workflow),
                stage,
                assignment,
                {"status": "passed", "status_reason": "ok"},
            )
            self.assertEqual(update["status"], "completed")
            hooks.run.assert_called()


class AcceptanceFromCheckTests(unittest.TestCase):
    def test_acceptance_copies_mapping_check_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_artifacts(workspace)
            (root / "custom_docs").mkdir(parents=True, exist_ok=True)
            (root / "custom_docs" / "a.txt").write_text("v1\n", encoding="utf-8")
            ctx = Context(
                root,
                workspace,
                "run-a",
                "map",
                1,
                "reviewer",
                "map.reviewer",
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-a", "calls": []}),
                encoding="utf-8",
            )
            record = _write_passed_check(ctx)
            lca_checks.record_acceptance(ctx)
            accepted = ctx.load_manifest()["accepted"][lca_checks.ACCEPTANCE_MODEL]
            self.assertEqual(accepted["inputs"]["files"], record["inputs"]["files"])
            self.assertEqual(
                accepted["model_fingerprint"],
                stable_hash(record["inputs"]["files"]),
            )

    def test_acceptance_uses_check_not_live_reviewer_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_artifacts(workspace)
            (root / "custom_docs").mkdir(parents=True, exist_ok=True)
            (root / "custom_docs" / "a.txt").write_text("v1\n", encoding="utf-8")
            (root / "reviewer_only").mkdir()
            (root / "reviewer_only" / "note.txt").write_text("r\n", encoding="utf-8")
            writer = Context(
                root,
                workspace,
                "run-b",
                "map",
                1,
                "executor",
                "map.executor",
                {"lca": {"phase": "mapping"}},
            )
            w_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="run-b",
                stage_id="map",
                assignment_id="map.executor",
                attempt=1,
                role="executor",
                metadata={"lca": {"phase": "mapping"}},
            )
            enrich_local_files(
                w_ctx,
                TaskBundle(
                    workflow_id="t",
                    stage_id="map",
                    assignment_id="map.executor",
                    role="executor",
                    max_attempts=1,
                    runtime_spec="x",
                    knowledge_sources=[
                        KnowledgeBinding(
                            "custom_docs", "local_dir", "custom_docs/", "local_files"
                        )
                    ],
                ),
            )
            writer.manifest.parent.mkdir(parents=True, exist_ok=True)
            writer.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-b", "calls": []}),
                encoding="utf-8",
            )
            record = _write_passed_check(writer)

            reviewer = Context(
                root,
                workspace,
                "run-b",
                "map",
                1,
                "reviewer",
                "map.reviewer",
                {"lca": {"phase": "mapping"}},
            )
            r_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="run-b",
                stage_id="map",
                assignment_id="map.reviewer",
                attempt=1,
                role="reviewer",
                metadata={"lca": {"phase": "mapping"}},
            )
            enrich_local_files(
                r_ctx,
                TaskBundle(
                    workflow_id="t",
                    stage_id="map",
                    assignment_id="map.reviewer",
                    role="reviewer",
                    max_attempts=1,
                    runtime_spec="x",
                    knowledge_sources=[
                        KnowledgeBinding(
                            "reviewer_only",
                            "local_dir",
                            "reviewer_only/",
                            "local_files",
                        )
                    ],
                ),
            )
            lca_checks.record_acceptance(reviewer)
            accepted = reviewer.load_manifest()["accepted"][lca_checks.ACCEPTANCE_MODEL]
            self.assertEqual(accepted["inputs"]["files"], record["inputs"]["files"])

    def test_mapping_knowledge_change_stales_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_artifacts(workspace)
            (root / "custom_docs").mkdir(parents=True, exist_ok=True)
            (root / "custom_docs" / "a.txt").write_text("v1\n", encoding="utf-8")
            ctx = Context(
                root,
                workspace,
                "run-c",
                "map",
                1,
                "reviewer",
                "map.reviewer",
                {"lca": {"phase": "mapping"}},
            )
            run_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="run-c",
                stage_id="map",
                assignment_id="map.reviewer",
                attempt=1,
                role="reviewer",
                metadata={"lca": {"phase": "mapping"}},
            )
            enrich_local_files(
                run_ctx,
                TaskBundle(
                    workflow_id="t",
                    stage_id="map",
                    assignment_id="map.reviewer",
                    role="reviewer",
                    max_attempts=1,
                    runtime_spec="x",
                    knowledge_sources=[
                        KnowledgeBinding(
                            "custom_docs", "local_dir", "custom_docs/", "local_files"
                        )
                    ],
                ),
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-c", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            lca_checks.record_acceptance(ctx)
            report = Context(
                root,
                workspace,
                "run-c",
                "report",
                1,
                "executor",
                "report.executor",
                {"lca": {"phase": "report"}},
            )
            lca_checks.require_approved_model(report)
            (root / "custom_docs" / "a.txt").write_text("v2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                lca_checks.require_approved_model(report)


class EvidenceFingerprintTests(unittest.TestCase):
    def _accept_and_stamp(self, root: Path, workspace: Path, run_id: str) -> Context:
        _seed_mapping_artifacts(workspace)
        (root / "custom_docs").mkdir(parents=True, exist_ok=True)
        (root / "custom_docs" / "a.txt").write_text("v1\n", encoding="utf-8")
        mapping = Context(
            root,
            workspace,
            run_id,
            "map",
            1,
            "reviewer",
            "map.reviewer",
            {"lca": {"phase": "mapping"}},
        )
        mapping.manifest.parent.mkdir(parents=True, exist_ok=True)
        mapping.manifest.write_text(
            json.dumps({"accepted": {}, "run_id": run_id, "calls": []}),
            encoding="utf-8",
        )
        _write_passed_check(mapping)
        lca_checks.record_acceptance(mapping)
        report = Context(
            root,
            workspace,
            run_id,
            "report",
            1,
            "executor",
            "report.executor",
            {"lca": {"phase": "report"}},
        )
        fp = lca_checks.evidence_model_fingerprint(report)
        artifact = (
            workspace
            / "outputs"
            / "reports"
            / "runs"
            / run_id
            / "report"
            / "1"
            / "call"
            / "raw.json"
        )
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps(
                {
                    "status": "success",
                    "operation_id": "op",
                    "request_id": "req",
                    "identity": {"run_id": run_id},
                    "success_count": 1,
                    "failed_count": 0,
                }
            ),
            encoding="utf-8",
        )
        manifest = report.load_manifest()
        manifest["calls"].append(
            {
                "call_id": "call",
                "tool": "import_lci",
                "stage": "report",
                "attempt": 1,
                "role": "executor",
                "arguments": {},
                "status": "success",
                "artifact": {
                    "path": str(artifact.relative_to(workspace)),
                    "sha256": "x",
                    "size_bytes": 1,
                },
                "model_fingerprint": fp,
            }
        )
        report.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        return report

    def test_report_only_knowledge_does_not_stale_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            report = self._accept_and_stamp(root, workspace, "run-e1")
            (root / "report_docs").mkdir()
            (root / "report_docs" / "g.txt").write_text("g\n", encoding="utf-8")
            r_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="run-e1",
                stage_id="report",
                assignment_id="report.executor",
                attempt=1,
                role="executor",
                metadata={"lca": {"phase": "report"}},
            )
            enrich_local_files(
                r_ctx,
                TaskBundle(
                    workflow_id="t",
                    stage_id="report",
                    assignment_id="report.executor",
                    role="executor",
                    max_attempts=1,
                    runtime_spec="x",
                    knowledge_sources=[
                        KnowledgeBinding(
                            "report_docs", "local_dir", "report_docs/", "local_files"
                        )
                    ],
                ),
            )
            # resolve_ref checks sha256 — bypass by patching load path via evidence
            # after fixing artifact hash
            from harness.runtime.hashing import sha256_file

            call = report.load_manifest()["calls"][0]
            path = workspace / call["artifact"]["path"]
            call["artifact"]["sha256"] = sha256_file(path)
            call["artifact"]["size_bytes"] = path.stat().st_size
            manifest = report.load_manifest()
            manifest["calls"] = [call]
            report.manifest.write_text(json.dumps(manifest), encoding="utf-8")
            pairs = lca_checks.evidence(report)
            self.assertEqual(len(pairs), 1)

    def test_report_writer_reviewer_knowledge_diff_does_not_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            report = self._accept_and_stamp(root, workspace, "run-e2")
            from harness.runtime.hashing import sha256_file

            call = report.load_manifest()["calls"][0]
            path = workspace / call["artifact"]["path"]
            call["artifact"]["sha256"] = sha256_file(path)
            call["artifact"]["size_bytes"] = path.stat().st_size
            manifest = report.load_manifest()
            manifest["calls"] = [call]
            report.manifest.write_text(json.dumps(manifest), encoding="utf-8")
            (root / "rev_docs").mkdir()
            (root / "rev_docs" / "n.txt").write_text("n\n", encoding="utf-8")
            r_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="run-e2",
                stage_id="report",
                assignment_id="report.reviewer",
                attempt=1,
                role="reviewer",
                metadata={"lca": {"phase": "report"}},
            )
            enrich_local_files(
                r_ctx,
                TaskBundle(
                    workflow_id="t",
                    stage_id="report",
                    assignment_id="report.reviewer",
                    role="reviewer",
                    max_attempts=1,
                    runtime_spec="x",
                    knowledge_sources=[
                        KnowledgeBinding(
                            "rev_docs", "local_dir", "rev_docs/", "local_files"
                        )
                    ],
                ),
            )
            reviewer = Context(
                root,
                workspace,
                "run-e2",
                "report",
                1,
                "reviewer",
                "report.reviewer",
                {"lca": {"phase": "report"}},
            )
            pairs = lca_checks.evidence(reviewer)
            self.assertEqual(len(pairs), 1)

    def test_accepted_model_input_change_stales_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            report = self._accept_and_stamp(root, workspace, "run-e3")
            from harness.runtime.hashing import sha256_file

            call = report.load_manifest()["calls"][0]
            path = workspace / call["artifact"]["path"]
            call["artifact"]["sha256"] = sha256_file(path)
            call["artifact"]["size_bytes"] = path.stat().st_size
            manifest = report.load_manifest()
            manifest["calls"] = [call]
            report.manifest.write_text(json.dumps(manifest), encoding="utf-8")
            (workspace / "inputs" / "plan.md").write_text(
                "# changed\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "stale"):
                lca_checks.evidence(report)


class GenericDependencyTests(unittest.TestCase):
    def test_generic_modules_do_not_import_lca(self) -> None:
        banned = (
            "harness.domains.lca",
            "harness.tools.control_openlca",
            "harness.tools.lca_artifacts",
        )
        for mod in list(sys.modules):
            if any(mod == b or mod.startswith(b + ".") for b in banned):
                del sys.modules[mod]
        importlib.invalidate_caches()
        import harness.runtime as runtime_mod
        import harness.runtime.knowledge_providers.local_files as local_mod
        import harness.workflows.lca_orchestrator.config_fingerprint as fp_mod

        del runtime_mod, local_mod, fp_mod
        loaded = [
            name
            for name in sys.modules
            if any(name == b or name.startswith(b + ".") for b in banned)
        ]
        self.assertEqual(loaded, [])


class PathSafetyTests(unittest.TestCase):
    def test_reuse_escape_rejected_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            with self.assertRaises(ValueError):
                resolve_project_path(root, "../../x.yaml", label="reuse")
            with self.assertRaises(ValueError):
                peek_capability_ids(
                    # fabricate path content via temp yaml
                    self._write_escape_yaml(root),
                    project_root=root,
                )

    def _write_escape_yaml(self, root: Path) -> Path:
        path = root / "harness" / "workflows" / "escape.yaml"
        path.write_text("reuse: ../../other.yaml\nid: x\n", encoding="utf-8")
        return path

    def test_resume_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            require_identifier("../x", label="run id")
        with self.assertRaises(ValueError):
            require_identifier("a/b", label="run id")

    def test_output_path_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _stage_payload()
            payload["stages"][0]["outputs"] = ["../../etc/passwd"]
            path = root / "harness" / "workflows" / "bad-out.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())
            payload["stages"][0]["outputs"] = ["/tmp/x"]
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())


class CapabilitiesCompositionTests(unittest.TestCase):
    def test_generic_workflow_gets_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _stage_payload(with_check=False)
            payload["capabilities"] = []
            path = root / "harness" / "workflows" / "generic.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            caps = compose_capabilities(peek_capability_ids(path, project_root=root))
            self.assertIn("local_files", caps.knowledge.known_ids())
            workflow = load_workflow(path, project_root=root, capabilities=caps)
            self.assertIn("local_files", caps.knowledge.known_ids())
            self.assertTrue(workflow.bundles)

    def test_task_and_workflow_same_capabilities(self) -> None:
        path = WORKFLOWS / "LCA-main.yaml"
        via_workflow = _capabilities_for(
            argparse.Namespace(task=None, workflow=path),
            PROJECT_ROOT,
            path,
        )
        via_task = _capabilities_for(
            argparse.Namespace(task="whole-lca", workflow=None),
            PROJECT_ROOT,
            path,
        )
        self.assertEqual(
            via_workflow.checkers.known_ids(), via_task.checkers.known_ids()
        )
        self.assertEqual(
            via_workflow.knowledge.known_ids(), via_task.knowledge.known_ids()
        )
        self.assertEqual(via_workflow.hooks.known_ids(), via_task.hooks.known_ids())

    def test_unknown_capability_fail_fast(self) -> None:
        with self.assertRaises(ValueError):
            compose_capabilities(["nope"])


class RuntimeVersionTests(unittest.TestCase):
    def test_initial_state_is_v3(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        state = initial_state(
            run_id="abc", task="whole-lca", worker="codex", workflow=workflow
        )
        self.assertEqual(state.get("runtime_version"), 3)

    def test_v3_matching_config_resumes(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_runtime_config(
                workspace,
                "run-v3",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="test-model",
            )
            assert_runtime_config_matches(
                workspace,
                "run-v3",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="test-model",
            )

    def test_missing_runtime_config_is_version_incompatible(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            with self.assertRaisesRegex(ValueError, "cannot be resumed by v3"):
                assert_runtime_config_matches(
                    workspace,
                    "missing",
                    workflow,
                    project_root=PROJECT_ROOT,
                    worker="codex",
                    model="test-model",
                )

    def test_fingerprint_change_still_rejects(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_runtime_config(
                workspace,
                "run-v3b",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="test-model",
            )
            path = workspace / "memory" / "evidence" / "run-v3b" / "runtime-config.json"
            stored = json.loads(path.read_text(encoding="utf-8"))
            stored["fingerprint"] = "tampered"
            path.write_text(json.dumps(stored), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "configuration changed"):
                assert_runtime_config_matches(
                    workspace,
                    "run-v3b",
                    workflow,
                    project_root=PROJECT_ROOT,
                    worker="codex",
                    model="test-model",
                )


class ListDeclarationTests(unittest.TestCase):
    def test_user_seq_forbidden(self) -> None:
        from harness.workflows.lca_orchestrator.lists import reject_user_seq_declaration

        with self.assertRaisesRegex(ValueError, "must not declare seq"):
            reject_user_seq_declaration({"seq": [{"add": ["a"]}]}, label="rules")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _stage_payload(with_check=False)
            payload["assignments"]["s1.executor"]["rules"] = {
                "seq": [{"add": ["paths"]}]
            }
            path = root / "harness" / "workflows" / "bad-seq.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "must not declare seq"):
                load_workflow(path, project_root=root, capabilities=base_capabilities())

    def test_nested_malformed_patch_fail_fast(self) -> None:
        with self.assertRaises(ValueError):
            parse_optional_list_field({"add": ["a"], "typo": ["b"]})
        merged = merge_list_declarations({"add": ["a"]}, {"add": ["b"]})
        with self.assertRaises(ValueError):
            resolve_list(["default"], {"seq": [{"add": ["x"], "typo": ["y"]}]})
        self.assertEqual(resolve_list(["default"], merged), ["default", "a", "b"])


class BaseCapabilitiesTests(unittest.TestCase):
    def test_base_registers_local_files(self) -> None:
        caps = base_capabilities()
        self.assertIn("local_files", caps.knowledge.known_ids())
        self.assertEqual(set(caps.checkers.known_ids()), set())


if __name__ == "__main__":
    unittest.main()
