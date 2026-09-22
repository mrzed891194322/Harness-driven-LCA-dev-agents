"""Merge-blocker regressions: defaults patch, evidence stale, phase, symlink, dupes."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from harness.domains.lca import checkers as lca_checkers
from harness.domains.lca import hooks as lca_hooks
from harness.domains.lca.bootstrap import lca_capabilities
from harness.runtime.context import RunContext
from harness.runtime.hashing import sha256_file
from harness.runtime.knowledge_providers.local_files import discover_files_at
from harness.tools.control_openlca.utils import workflow as openlca_workflow
from harness.tools.lca_artifacts import checks as lca_checks
from harness.tools.lca_artifacts.store import Context
from harness.workflows.lca_orchestrator.loader import load_workflow
from harness.workflows.lca_orchestrator.models import Workflow
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.openlca_fakes import write_product_system_fixture

REQUIRED_DEFAULT_RULES = ("workspace_boundary", "runtime", "paths")


def _tree(root: Path) -> None:
    specs = root / "harness" / "specs" / "s1"
    specs.mkdir(parents=True)
    (specs / "README.md").write_text("# stage\n", encoding="utf-8")
    (specs / "executor.md").write_text("role=executor\n", encoding="utf-8")
    (specs / "reviewer.md").write_text("role=reviewer\n", encoding="utf-8")
    rules = root / "harness" / "rules" / "project"
    rules.mkdir(parents=True)
    for name in ("write-boundary.md", "runtime.md", "paths.md", "company.md"):
        (rules / name).write_text(f"# {name}\n", encoding="utf-8")
    runtime = root / "harness" / "specs" / "public" / "references"
    runtime.mkdir(parents=True)
    (runtime / "workflow-runtime-spec.md").write_text("# runtime\n", encoding="utf-8")
    tools = root / "harness" / "tools" / "lca_artifacts"
    tools.mkdir(parents=True)
    (tools / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "harness" / "workflows").mkdir(parents=True)
    (root / "harness" / "knowledge").mkdir(parents=True)
    (root / "harness" / "knowledge2").mkdir(parents=True)


def _base_payload() -> dict:
    return {
        "id": "base",
        "capabilities": ["lca"],
        "runtime_spec": "harness/specs/public/references/workflow-runtime-spec.md",
        "registry": {
            "rules": {
                "workspace_boundary": "harness/rules/project/write-boundary.md",
                "runtime": "harness/rules/project/runtime.md",
                "paths": "harness/rules/project/paths.md",
                "company_rule": "harness/rules/project/company.md",
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
                "extra_knowledge": {
                    "kind": "local_dir",
                    "path": "harness/knowledge2/",
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
                "context": {"lca": {"phase": "mapping"}},
                "max_attempts": 3,
                "outputs": ["workspace/outputs/inventory/process-mapping.json"],
                "checks": [{"id": "lca.mapping"}],
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


def _seed_mapping_workspace(workspace: Path) -> None:
    inv = workspace / "outputs" / "inventory"
    inv.mkdir(parents=True)
    (workspace / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace / "inputs" / "plan.md").write_text("# plan\n", encoding="utf-8")
    (inv / "extracted-bom.json").write_text("{}", encoding="utf-8")
    (inv / "process-mapping.json").write_text("{}", encoding="utf-8")
    lci = workspace / "outputs" / "LCI" / "flows"
    lci.mkdir(parents=True)
    (lci / "f.json").write_text("{}", encoding="utf-8")


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


def _append_evidence_call(
    ctx: Context, *, tool: str, stage: str, payload: dict
) -> dict:
    raw_dir = (
        ctx.workspace
        / "outputs"
        / "reports"
        / "runs"
        / ctx.run_id
        / stage
        / str(ctx.attempt)
        / "call-extra"
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "raw.json"
    raw_path.write_text(json.dumps(payload), encoding="utf-8")
    ref = {
        "path": str(raw_path.relative_to(ctx.workspace)),
        "sha256": sha256_file(raw_path),
        "size_bytes": raw_path.stat().st_size,
    }
    manifest = ctx.load_manifest()
    manifest.setdefault("calls", []).append(
        {
            "tool": tool,
            "stage": stage,
            "attempt": ctx.attempt,
            "artifact": ref,
        }
    )
    ctx.manifest.write_text(json.dumps(manifest), encoding="utf-8")
    return ref


class DefaultsRulesLiveBundlesTests(unittest.TestCase):
    def test_whole_lca_bundles_keep_default_rules(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        for assignment_id, bundle in workflow.bundles.items():
            for rule_id in REQUIRED_DEFAULT_RULES:
                self.assertIn(rule_id, bundle.rule_ids, msg=assignment_id)
            self.assertIn("lca_method", bundle.rule_ids, msg=assignment_id)
            self.assertIn("knowledge_files", bundle.rule_ids, msg=assignment_id)
            if bundle.role == "reviewer":
                self.assertIn("reviewer_readonly", bundle.rule_ids, msg=assignment_id)
            if "lca_artifacts" in bundle.tool_ids:
                self.assertIn("artifact_usage", bundle.rule_ids, msg=assignment_id)
            if "control_openlca" in bundle.tool_ids:
                self.assertIn("openlca_usage", bundle.rule_ids, msg=assignment_id)

    def test_revise_lca_bundles_keep_default_rules(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-revise.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        for assignment_id, bundle in workflow.bundles.items():
            for rule_id in REQUIRED_DEFAULT_RULES:
                self.assertIn(rule_id, bundle.rule_ids, msg=assignment_id)
            self.assertIn("user_intent", bundle.rule_ids, msg=assignment_id)
            self.assertIn("lca_method", bundle.rule_ids, msg=assignment_id)
            self.assertIn("knowledge_files", bundle.rule_ids, msg=assignment_id)


class DefaultsReusePatchTests(unittest.TestCase):
    def _load_overlay(self, root: Path, defaults_overlay: dict) -> Workflow:
        base = _base_payload()
        base_path = root / "harness" / "workflows" / "base.yaml"
        base_path.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
        overlay = {
            "id": "overlay",
            "reuse": "harness/workflows/base.yaml",
            "defaults": defaults_overlay,
        }
        path = root / "harness" / "workflows" / "overlay.yaml"
        path.write_text(yaml.safe_dump(overlay, allow_unicode=True), encoding="utf-8")
        return load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_defaults_rules_overlay_add(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workflow = self._load_overlay(root, {"rules": {"add": ["company_rule"]}})
            self.assertEqual(
                workflow.default_rules,
                ["workspace_boundary", "runtime", "paths", "company_rule"],
            )

    def test_defaults_rules_overlay_remove(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workflow = self._load_overlay(root, {"rules": {"remove": ["paths"]}})
            self.assertEqual(workflow.default_rules, ["workspace_boundary", "runtime"])

    def test_defaults_rules_overlay_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workflow = self._load_overlay(root, {"rules": ["company_rule"]})
            self.assertEqual(workflow.default_rules, ["company_rule"])

    def test_defaults_rules_overlay_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workflow = self._load_overlay(root, {"rules": []})
            self.assertEqual(workflow.default_rules, [])

    def test_defaults_knowledge_overlay_add_remove(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            workflow = self._load_overlay(
                root, {"knowledge": {"add": ["extra_knowledge"]}}
            )
            self.assertEqual(
                workflow.default_knowledge,
                ["workspace_knowledge", "extra_knowledge"],
            )
            workflow2 = self._load_overlay(
                root, {"knowledge": {"remove": ["workspace_knowledge"]}}
            )
            self.assertEqual(workflow2.default_knowledge, [])

    def test_defaults_patch_plus_overlay_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            base = _base_payload()
            base["defaults"]["rules"] = {"add": ["workspace_boundary", "runtime"]}
            base_path = root / "harness" / "workflows" / "base.yaml"
            base_path.write_text(
                yaml.safe_dump(base, allow_unicode=True), encoding="utf-8"
            )
            overlay = {
                "id": "overlay",
                "reuse": "harness/workflows/base.yaml",
                "defaults": {"rules": {"add": ["paths", "company_rule"]}},
            }
            path = root / "harness" / "workflows" / "overlay.yaml"
            path.write_text(
                yaml.safe_dump(overlay, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            self.assertEqual(
                workflow.default_rules,
                ["workspace_boundary", "runtime", "paths", "company_rule"],
            )


class ReviewOnlyChecksTests(unittest.TestCase):
    def test_review_only_empty_checks_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _base_payload()
            payload["stages"] = [
                {
                    "id": "intake",
                    "spec": "harness/specs/s1/README.md",
                    "outputs": ["workspace/memory/reviews/note.md"],
                    "checks": [],
                    "steps": [{"assignment": "intake.reviewer"}],
                }
            ]
            payload["assignments"] = {
                "intake.reviewer": {
                    "role": "reviewer",
                    "task_spec": "harness/specs/s1/reviewer.md",
                    "tools": [],
                }
            }
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_review_only_with_checks_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _base_payload()
            payload["stages"] = [
                {
                    "id": "intake",
                    "spec": "harness/specs/s1/README.md",
                    "outputs": ["workspace/memory/reviews/note.md"],
                    "checks": [{"id": "lca.mapping"}],
                    "steps": [{"assignment": "intake.reviewer"}],
                }
            ]
            payload["assignments"] = {
                "intake.reviewer": {
                    "role": "reviewer",
                    "task_spec": "harness/specs/s1/reviewer.md",
                    "tools": [],
                }
            }
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "review-only stage"):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())


class DuplicateIdsTests(unittest.TestCase):
    def test_duplicate_checker_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _base_payload()
            payload["stages"][0]["checks"] = [
                {"id": "lca.mapping"},
                {"id": "lca.mapping"},
            ]
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "duplicate checker"):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_duplicate_hook_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _base_payload()
            payload["stages"][0]["hooks"] = {
                "on_reviewer_passed": [
                    "lca.record_acceptance",
                    "lca.record_acceptance",
                ]
            }
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "duplicate id"):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())


class LcaPhaseFailClosedTests(unittest.TestCase):
    def test_checker_phase_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            run_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="r1",
                stage_id="s1",
                attempt=1,
                role="executor",
                assignment_id="s1.executor",
                metadata={"lca": {"phase": "report"}},
            )
            with self.assertRaisesRegex(ValueError, "phase mismatch"):
                lca_checkers._run_validate(run_ctx, "mapping")

    def test_missing_phase_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            run_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="r1",
                stage_id="s1",
                attempt=1,
                role="executor",
                assignment_id="s1.executor",
                metadata={},
            )
            with self.assertRaisesRegex(ValueError, "phase is required"):
                lca_checkers._run_validate(run_ctx, "mapping")

    def test_record_acceptance_rejects_report_phase(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            run_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="r1",
                stage_id="s1",
                attempt=1,
                role="reviewer",
                assignment_id="s1.reviewer",
                metadata={"lca": {"phase": "report"}},
            )
            with self.assertRaisesRegex(ValueError, "phase == 'mapping'"):
                lca_hooks._record_acceptance(run_ctx)

    def test_acceptance_rejects_other_stage_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_workspace(workspace)
            old = Context(
                root,
                workspace,
                "run-a",
                "old-mapping",
                1,
                "reviewer",
                "old.reviewer",
                {"lca": {"phase": "mapping"}},
            )
            old.manifest.parent.mkdir(parents=True, exist_ok=True)
            old.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-a", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(old)
            current = Context(
                root,
                workspace,
                "run-a",
                "03-dataset-mapping",
                1,
                "reviewer",
                "map.reviewer",
                {"lca": {"phase": "mapping"}},
            )
            with self.assertRaisesRegex(ValueError, "producer stage"):
                lca_checks.record_acceptance(current)


class EvidenceStaleTests(unittest.TestCase):
    def test_new_relevant_evidence_call_makes_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_workspace(workspace)
            ctx = Context(
                root,
                workspace,
                "run-e",
                "03-dataset-mapping",
                1,
                "executor",
                "map.executor",
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-e", "calls": []}),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            _append_evidence_call(
                ctx,
                tool="validate_providers_batch",
                stage="03-dataset-mapping",
                payload={"ok": True},
            )
            state = lca_checks.validation_state(ctx, "mapping")
            self.assertEqual(state["status"], "stale")

    def test_frozen_evidence_modified_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_workspace(workspace)
            ctx = Context(
                root,
                workspace,
                "run-e2",
                "03-dataset-mapping",
                1,
                "executor",
                "map.executor",
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-e2", "calls": []}),
                encoding="utf-8",
            )
            ref = _append_evidence_call(
                ctx,
                tool="preflight_import_lci",
                stage="03-dataset-mapping",
                payload={"ok": True},
            )
            _write_passed_check(ctx)
            raw = workspace / ref["path"]
            raw.write_text(json.dumps({"ok": False}), encoding="utf-8")
            state = lca_checks.validation_state(ctx, "mapping")
            self.assertEqual(state["status"], "stale")

    def test_frozen_evidence_deleted_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_workspace(workspace)
            ctx = Context(
                root,
                workspace,
                "run-e3",
                "03-dataset-mapping",
                1,
                "executor",
                "map.executor",
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-e3", "calls": []}),
                encoding="utf-8",
            )
            ref = _append_evidence_call(
                ctx,
                tool="preflight_import_lci",
                stage="03-dataset-mapping",
                payload={"ok": True},
            )
            _write_passed_check(ctx)
            (workspace / ref["path"]).unlink()
            state = lca_checks.validation_state(ctx, "mapping")
            self.assertEqual(state["status"], "stale")

    def test_reviewer_knowledge_change_not_false_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            _seed_mapping_workspace(workspace)
            knowledge = root / "harness" / "knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / "a.txt").write_text("v1\n", encoding="utf-8")
            ctx = Context(
                root,
                workspace,
                "run-e4",
                "03-dataset-mapping",
                1,
                "executor",
                "map.executor",
                {"lca": {"phase": "mapping"}},
            )
            ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
            ctx.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-e4", "calls": []}),
                encoding="utf-8",
            )
            sources = (
                workspace
                / "memory"
                / "evidence"
                / "run-e4"
                / "sources"
                / "map.executor.json"
            )
            sources.parent.mkdir(parents=True, exist_ok=True)
            sources.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "harness/knowledge/a.txt",
                                "sha256": sha256_file(knowledge / "a.txt"),
                                "readable": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            _write_passed_check(ctx)
            (knowledge / "a.txt").write_text("v1\n", encoding="utf-8")
            (knowledge / "reviewer-only.txt").write_text("note\n", encoding="utf-8")
            state = lca_checks.validation_state(ctx, "mapping")
            self.assertEqual(state["status"], "passed")


class SymlinkContainmentTests(unittest.TestCase):
    def test_knowledge_symlink_inside_project_outside_root_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "proj"
            root.mkdir()
            knowledge = root / "harness" / "knowledge"
            knowledge.mkdir(parents=True)
            secret = root / "private" / "secret.txt"
            secret.parent.mkdir(parents=True)
            secret.write_text("secret\n", encoding="utf-8")
            (knowledge / "link.txt").symlink_to(secret)
            payload = discover_files_at(root, "harness/knowledge/")
            self.assertTrue(payload["files"])
            self.assertFalse(payload["files"][0]["readable"])
            self.assertIn("knowledge root", payload["files"][0]["error"])

    def test_rule_symlink_outside_project_load_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "proj"
            outside = Path(temp_dir) / "outside.md"
            outside.write_text("# outside\n", encoding="utf-8")
            _tree(root)
            (root / "harness" / "rules" / "project" / "paths.md").unlink()
            (root / "harness" / "rules" / "project" / "paths.md").symlink_to(outside)
            payload = _base_payload()
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_task_spec_symlink_outside_project_load_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "proj"
            outside = Path(temp_dir) / "outside.md"
            outside.write_text("role=executor\n", encoding="utf-8")
            _tree(root)
            (root / "harness" / "specs" / "s1" / "executor.md").unlink()
            (root / "harness" / "specs" / "s1" / "executor.md").symlink_to(outside)
            payload = _base_payload()
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_knowledge_root_symlink_outside_load_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "proj"
            outside = Path(temp_dir) / "outside_knowledge"
            outside.mkdir()
            _tree(root)
            target = root / "harness" / "knowledge"
            # replace dir with symlink
            for child in target.iterdir():
                child.unlink()
            target.rmdir()
            target.symlink_to(outside, target_is_directory=True)
            payload = _base_payload()
            path = root / "harness" / "workflows" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=lca_capabilities())

    def test_snapshot_post_symlink_escape_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "proj"
            root.mkdir()
            workspace = root / "workspace"
            workspace.mkdir()
            knowledge = root / "harness" / "knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / "a.txt").write_text("ok\n", encoding="utf-8")
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
            entry = {
                "scope": "project",
                "path": "harness/knowledge/a.txt",
                "sha256": sha256_file(knowledge / "a.txt"),
            }
            outside = Path(temp_dir) / "outside.txt"
            outside.write_text("escaped\n", encoding="utf-8")
            (knowledge / "a.txt").unlink()
            (knowledge / "a.txt").symlink_to(outside)
            current = lca_checks.snapshot_current_hashes(ctx, {"files": [entry]})
            self.assertNotEqual(current[0]["sha256"], entry["sha256"])
            self.assertEqual(current[0]["sha256"], "missing")

    def test_lci_entity_symlink_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            (root / "human_readable_mapping.md").write_text(
                "# Mapping\n", encoding="utf-8"
            )
            flow = next((root / "flows").glob("*.json"))
            outside = root.parent / f"{root.name}-outside.json"
            outside.write_text(flow.read_text(encoding="utf-8"), encoding="utf-8")
            flow.unlink()
            flow.symlink_to(outside)
            result = openlca_workflow.validate_lci_directory(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("symbolic link" in error for error in result["errors"]))

    def test_human_readable_mapping_symlink_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            outside = root.parent / f"{root.name}-mapping.md"
            outside.write_text("# Mapping\n", encoding="utf-8")
            mapping = root / "human_readable_mapping.md"
            mapping.symlink_to(outside)
            result = openlca_workflow.validate_lci_directory(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("symbolic link" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
