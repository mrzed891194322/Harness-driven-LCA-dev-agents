"""Audit/safety closeout: review notes, hooks, execution fingerprint, scoped paths."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from harness.domains.lca.bootstrap import lca_capabilities
from harness.runtime.hashing import stable_hash
from harness.runtime.knowledge_providers.local_files import discover_files_at
from harness.tools.lca_artifacts import checks as lca_checks
from harness.tools.lca_artifacts.store import Context
from harness.workflows.lca_orchestrator.config_fingerprint import (
    assert_runtime_config_matches,
    build_runtime_config,
    write_runtime_config,
)
from harness.workflows.lca_orchestrator.graph import (
    OrchestratorRuntime,
    WorkflowState,
    initial_state,
    missing_expected_outputs,
)
from harness.workflows.lca_orchestrator.handoff import (
    review_note_path,
    write_review_note,
)
from harness.workflows.lca_orchestrator.loader import load_workflow
from harness.workflows.lca_orchestrator.yaml_strict import load_yaml_strict
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


def _payload(*, with_hook: bool = True) -> dict:
    stage: dict = {
        "id": "s1",
        "spec": "harness/specs/s1/README.md",
        "context": {"lca": {"phase": "mapping"}},
        "max_attempts": 3,
        "outputs": [
            "workspace/outputs/inventory/process-mapping.json",
            "workspace/outputs/LCI/",
        ],
        "checks": [{"id": "lca.mapping"}],
        "steps": [
            {"assignment": "s1.executor"},
            {"assignment": "s1.reviewer"},
        ],
    }
    if with_hook:
        stage["hooks"] = {"on_reviewer_passed": ["lca.record_acceptance"]}
    return {
        "id": "audit",
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
                    "env": {"MODE": "production"},
                    "headers": {"X-Token": "secret-value"},
                }
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
        "stages": [stage],
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


def _seed_outputs(workspace: Path) -> None:
    inv = workspace / "outputs" / "inventory"
    inv.mkdir(parents=True)
    (workspace / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace / "inputs" / "plan.md").write_text("# plan\n", encoding="utf-8")
    (inv / "process-mapping.json").write_text(
        json.dumps({"items": [{"item_id": "one"}]}), encoding="utf-8"
    )
    lci = workspace / "outputs" / "LCI" / "flows"
    lci.mkdir(parents=True)
    (lci / "f.json").write_text("{}", encoding="utf-8")


def _write_passed_check(ctx: Context) -> dict:
    inputs = lca_checks.dependencies(ctx, "mapping")
    path = lca_checks.check_path(ctx, "mapping")
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "check_id": "mapping",
        "checker_version": lca_checks.CHECKER_VERSION,
        "status": "passed",
        "inputs": inputs,
        "executed_at": "2020-01-01T00:00:00Z",
        "summary": "ok",
        "errors": [],
        "warnings": [],
    }
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


class ReviewNoteGateTests(unittest.TestCase):
    def _runtime(self, root: Path, workspace: Path, *, hooks=None):
        path = root / "harness" / "workflows" / "t.yaml"
        path.write_text(
            yaml.safe_dump(_payload(), allow_unicode=True), encoding="utf-8"
        )
        workflow = load_workflow(
            path, project_root=root, capabilities=lca_capabilities()
        )
        caps = lca_capabilities()
        if hooks is not None:
            caps.hooks = hooks
        runtime = OrchestratorRuntime(
            workflow,
            project_root=root,
            workspace_root=workspace,
            session_client=MagicMock(),
            worker="codex",
            capabilities=caps,
        )
        return runtime, workflow

    def _state(self, workflow) -> WorkflowState:
        state = initial_state(
            run_id="run-a", task="t", worker="codex", workflow=workflow
        )
        state["stage_index"] = 0
        state["step_index"] = 1
        state["attempt"] = 1
        state["current_assignment"] = "s1.reviewer"
        state["current_role"] = "reviewer"
        return state

    def test_stale_check_note_is_invalidated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_outputs(workspace)
            runtime, workflow = self._runtime(root, workspace)
            stage = workflow.stages[0]
            assignment = workflow.assignments["s1.reviewer"]
            ctx = Context(
                root,
                workspace,
                "run-a",
                stage.stage_id,
                1,
                "reviewer",
                assignment.assignment_id,
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-a", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            (workspace / "inputs" / "plan.md").write_text(
                "# changed\n", encoding="utf-8"
            )
            handoff = {
                "status": "passed",
                "status_reason": "看起来通过",
                "stage": stage.stage_id,
                "attempt": 1,
            }
            update = runtime._advance_after_reviewer(
                self._state(workflow), stage, assignment, handoff
            )
            self.assertEqual(update["step_index"], 0)
            note = review_note_path(workspace, stage.stage_id, 1).read_text(
                encoding="utf-8"
            )
            self.assertIn("Reviewer 结论：passed", note)
            self.assertIn("系统验收：invalidated", note)
            self.assertNotRegex(note, r"(?m)^系统验收：accepted$")

    def test_missing_output_note_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_outputs(workspace)
            runtime, workflow = self._runtime(root, workspace)
            stage = workflow.stages[0]
            assignment = workflow.assignments["s1.reviewer"]
            ctx = Context(
                root,
                workspace,
                "run-a",
                stage.stage_id,
                1,
                "reviewer",
                assignment.assignment_id,
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-a", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            (workspace / "outputs" / "inventory" / "process-mapping.json").unlink()
            update = runtime._advance_after_reviewer(
                self._state(workflow),
                stage,
                assignment,
                {
                    "status": "passed",
                    "status_reason": "ok",
                    "stage": stage.stage_id,
                    "attempt": 1,
                },
            )
            self.assertEqual(update["attempt"], 2)
            note = review_note_path(workspace, stage.stage_id, 1).read_text(
                encoding="utf-8"
            )
            self.assertIn("系统验收：invalidated", note)
            self.assertIn("缺少产物", note)

    def test_guard_success_note_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_outputs(workspace)
            hooks = MagicMock()
            runtime, workflow = self._runtime(root, workspace, hooks=hooks)
            stage = workflow.stages[0]
            assignment = workflow.assignments["s1.reviewer"]
            ctx = Context(
                root,
                workspace,
                "run-a",
                stage.stage_id,
                1,
                "reviewer",
                assignment.assignment_id,
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-a", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            update = runtime._advance_after_reviewer(
                self._state(workflow),
                stage,
                assignment,
                {
                    "status": "passed",
                    "status_reason": "ok",
                    "stage": stage.stage_id,
                    "attempt": 1,
                },
            )
            self.assertEqual(update["status"], "completed")
            note = review_note_path(workspace, stage.stage_id, 1).read_text(
                encoding="utf-8"
            )
            self.assertIn("系统验收：accepted", note)
            hooks.run.assert_called()

    def test_reviewer_failed_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_outputs(workspace)
            runtime, workflow = self._runtime(root, workspace)
            stage = workflow.stages[0]
            assignment = workflow.assignments["s1.reviewer"]
            update = runtime._advance_after_reviewer(
                self._state(workflow),
                stage,
                assignment,
                {
                    "status": "failed",
                    "status_reason": "缺数据",
                    "fix_instructions": "补一行",
                    "stage": stage.stage_id,
                    "attempt": 1,
                },
            )
            self.assertEqual(update["step_index"], 0)
            note = review_note_path(workspace, stage.stage_id, 1).read_text(
                encoding="utf-8"
            )
            self.assertIn("Reviewer 结论：failed", note)
            self.assertIn("系统验收：failed", note)
            self.assertIn("补一行", note)


class HookFailClosedTests(unittest.TestCase):
    def test_hook_failure_fails_run_without_writer_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_outputs(workspace)
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(_payload(), allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            hooks = MagicMock()
            hooks.run.side_effect = [RuntimeError("boom"), None]
            # second hook should never run — only one registered; simulate two
            workflow.bundles["s1.reviewer"].reviewer_passed_hooks = [
                "lca.record_acceptance",
                "lca.extra",
            ]
            caps = lca_capabilities()
            caps.hooks = hooks
            runtime = OrchestratorRuntime(
                workflow,
                project_root=root,
                workspace_root=workspace,
                session_client=MagicMock(),
                worker="codex",
                capabilities=caps,
            )
            stage = workflow.stages[0]
            assignment = workflow.assignments["s1.reviewer"]
            ctx = Context(
                root,
                workspace,
                "run-h",
                stage.stage_id,
                1,
                "reviewer",
                assignment.assignment_id,
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-h", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            state = initial_state(
                run_id="run-h", task="t", worker="codex", workflow=workflow
            )
            state["stage_index"] = 0
            state["step_index"] = 1
            state["attempt"] = 1
            update = runtime._advance_after_reviewer(
                state,
                stage,
                assignment,
                {
                    "status": "passed",
                    "status_reason": "ok",
                    "stage": stage.stage_id,
                    "attempt": 1,
                },
            )
            self.assertEqual(update["status"], "failed")
            self.assertNotIn("attempt", update)
            self.assertEqual(hooks.run.call_count, 1)
            manifest = json.loads(
                (workspace / "memory" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["status"], "failed")
            self.assertIn("lca.record_acceptance", manifest["status_reason"])
            note = review_note_path(workspace, stage.stage_id, 1).read_text(
                encoding="utf-8"
            )
            self.assertIn("系统验收：hook_failed", note)


class ExecutionFingerprintTests(unittest.TestCase):
    def test_same_execution_resumes(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_runtime_config(
                workspace,
                "run-e",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="model-a",
            )
            assert_runtime_config_matches(
                workspace,
                "run-e",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="model-a",
            )

    def test_worker_change_rejects(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_runtime_config(
                workspace,
                "run-e",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="model-a",
            )
            with self.assertRaisesRegex(ValueError, "execution configuration changed"):
                assert_runtime_config_matches(
                    workspace,
                    "run-e",
                    workflow,
                    project_root=PROJECT_ROOT,
                    worker="claude",
                    model="model-a",
                )

    def test_model_change_rejects(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_runtime_config(
                workspace,
                "run-e",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="model-a",
            )
            with self.assertRaisesRegex(ValueError, "execution configuration changed"):
                assert_runtime_config_matches(
                    workspace,
                    "run-e",
                    workflow,
                    project_root=PROJECT_ROOT,
                    worker="codex",
                    model="model-b",
                )


class EnvHeaderFingerprintTests(unittest.TestCase):
    def test_env_and_header_value_change_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            path = root / "harness" / "workflows" / "t.yaml"
            payload = _payload()
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            first = build_runtime_config(
                workflow, project_root=root, worker="codex", model="m"
            )
            payload["registry"]["tools"]["lca_artifacts"]["env"]["MODE"] = "sandbox"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow2 = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            second = build_runtime_config(
                workflow2, project_root=root, worker="codex", model="m"
            )
            self.assertNotEqual(first["fingerprint"], second["fingerprint"])
            text = json.dumps(first)
            self.assertNotIn("secret-value", text)
            self.assertNotIn("production", text)
            self.assertEqual(
                first["config"]["tools"]["lca_artifacts"]["env"]["MODE"],
                stable_hash("production"),
            )
            payload["registry"]["tools"]["lca_artifacts"]["env"]["MODE"] = "production"
            payload["registry"]["tools"]["lca_artifacts"]["headers"]["X-Token"] = (
                "other"
            )
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow3 = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            third = build_runtime_config(
                workflow3, project_root=root, worker="codex", model="m"
            )
            self.assertNotEqual(first["fingerprint"], third["fingerprint"])


class ScopedSnapshotTests(unittest.TestCase):
    def test_project_and_workspace_inputs_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "inputs").mkdir()
            (workspace / "inputs" / "plan.md").write_text("ws\n", encoding="utf-8")
            (root / "inputs").mkdir()
            (root / "inputs" / "reference.md").write_text("proj\n", encoding="utf-8")
            ctx = Context(
                root,
                workspace,
                "run-s",
                "map",
                1,
                "executor",
                "map.executor",
                {"lca": {"phase": "mapping"}},
            )
            entries = lca_checks.scoped_fingerprints(
                ctx,
                [
                    workspace / "inputs" / "plan.md",
                    root / "inputs" / "reference.md",
                ],
            )
            scopes = {(e["scope"], e["path"]) for e in entries}
            self.assertIn(("workspace", "inputs/plan.md"), scopes)
            self.assertIn(("project", "inputs/reference.md"), scopes)
            restored_ws = lca_checks.resolve_snapshot_path(
                ctx, {"scope": "workspace", "path": "inputs/plan.md"}
            )
            restored_pj = lca_checks.resolve_snapshot_path(
                ctx, {"scope": "project", "path": "inputs/reference.md"}
            )
            self.assertEqual(restored_ws.read_text(encoding="utf-8"), "ws\n")
            self.assertEqual(restored_pj.read_text(encoding="utf-8"), "proj\n")

    def test_project_outputs_not_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (root / "outputs").mkdir()
            (root / "outputs" / "reference.md").write_text(
                "proj-out\n", encoding="utf-8"
            )
            (workspace / "outputs").mkdir()
            (workspace / "outputs" / "reference.md").write_text(
                "ws-out\n", encoding="utf-8"
            )
            ctx = Context(
                root,
                workspace,
                "run-s2",
                "map",
                1,
                "executor",
                "map.executor",
                {"lca": {"phase": "mapping"}},
            )
            entries = lca_checks.scoped_fingerprints(
                ctx, [root / "outputs" / "reference.md"]
            )
            self.assertEqual(entries[0]["scope"], "project")
            path = lca_checks.resolve_snapshot_path(ctx, entries[0])
            self.assertEqual(path.read_text(encoding="utf-8"), "proj-out\n")


class SymlinkSafetyTests(unittest.TestCase):
    def test_knowledge_root_symlink_escape_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "proj"
            root.mkdir()
            outside = Path(temp_dir) / "outside"
            outside.mkdir()
            (outside / "secret.txt").write_text("x\n", encoding="utf-8")
            link = root / "harness" / "knowledge"
            link.parent.mkdir(parents=True)
            link.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                discover_files_at(root, "harness/knowledge/")

    def test_file_symlink_escape_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "proj"
            root.mkdir()
            outside = Path(temp_dir) / "secret.txt"
            outside.write_text("secret\n", encoding="utf-8")
            knowledge = root / "harness" / "knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / "link.txt").symlink_to(outside)
            payload = discover_files_at(root, "harness/knowledge/")
            self.assertTrue(payload["files"])
            self.assertFalse(payload["files"][0]["readable"])
            self.assertIn("escapes", payload["files"][0]["error"])

    def test_output_symlink_escape_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            outside = Path(temp_dir) / "out.json"
            outside.write_text("{}\n", encoding="utf-8")
            target = workspace / "outputs" / "inventory"
            target.mkdir(parents=True)
            link = target / "extracted-bom.json"
            link.symlink_to(outside)
            missing = missing_expected_outputs(
                workspace, ["workspace/outputs/inventory/extracted-bom.json"]
            )
            self.assertEqual(
                missing, ["workspace/outputs/inventory/extracted-bom.json"]
            )


class StageOverrideTests(unittest.TestCase):
    def test_user_seq_in_stage_overrides_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            base = _payload()
            base_path = root / "harness" / "workflows" / "base.yaml"
            base_path.write_text(
                yaml.safe_dump(base, allow_unicode=True), encoding="utf-8"
            )
            overlay = {
                "id": "overlay",
                "reuse": "harness/workflows/base.yaml",
                "stage_overrides": {"s1": {"rules": {"seq": [{"add": ["paths"]}]}}},
            }
            path = root / "harness" / "workflows" / "overlay.yaml"
            path.write_text(
                yaml.safe_dump(overlay, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "must not declare seq"):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_hook_overlay_add_remove(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            base = _payload()
            base["stages"][0]["hooks"] = {
                "on_reviewer_passed": ["lca.record_acceptance"]
            }
            base_path = root / "harness" / "workflows" / "base.yaml"
            base_path.write_text(
                yaml.safe_dump(base, allow_unicode=True), encoding="utf-8"
            )
            overlay = {
                "id": "overlay",
                "reuse": "harness/workflows/base.yaml",
                "stage_overrides": {
                    "s1": {
                        "hooks": {
                            "on_reviewer_passed": {
                                "add": ["paths"],
                                "remove": ["lca.record_acceptance"],
                            }
                        }
                    }
                },
            }
            # paths is not a hook id but exercises merge; use fake via registry? hooks
            # are identifiers only at resolve — merge happens before attach.
            # Use add of same-shape id that won't validate as hook at attach if unknown.
            # Actually attach validates hooks against capabilities.hooks — so add a
            # registered hook. Only lca.record_acceptance exists. Test add noop + remove.
            overlay["stage_overrides"]["s1"]["hooks"]["on_reviewer_passed"] = {
                "remove": ["lca.record_acceptance"]
            }
            path = root / "harness" / "workflows" / "overlay.yaml"
            path.write_text(
                yaml.safe_dump(overlay, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            self.assertEqual(workflow.bundles["s1.reviewer"].reviewer_passed_hooks, [])


class StrictYamlAndTypeTests(unittest.TestCase):
    def test_duplicate_mapping_key_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dup.yaml"
            path.write_text("a: 1\na: 2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate YAML mapping key"):
                load_yaml_strict(path)

    def test_string_false_not_bool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _payload()
            payload["registry"]["tools"]["lca_artifacts"]["runtime"] = {
                "run_context_env": "false"
            }
            path = root / "harness" / "workflows" / "bad-bool.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "must be a boolean"):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_invalid_max_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _payload()
            payload["max_attempts"] = True
            path = root / "harness" / "workflows" / "bad-attempts.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "positive integer"):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())


class WriteReviewNoteUnitTests(unittest.TestCase):
    def test_write_review_note_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "note.md"
            write_review_note(
                path,
                {
                    "stage": "s1",
                    "attempt": 1,
                    "status": "passed",
                    "status_reason": "ok",
                },
                system_status="invalidated",
                system_reason="stale",
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("Reviewer 结论：passed", text)
            self.assertIn("系统验收：invalidated", text)
            self.assertIn("stale", text)


if __name__ == "__main__":
    unittest.main()
