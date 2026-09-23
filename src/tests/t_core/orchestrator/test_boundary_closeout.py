"""Boundary closeout regressions: metadata, acceptance, reuse seq, topology, resume."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from core.runtime.capabilities import base_capabilities, empty_capabilities
from core.runtime.context import RunContext
from core.runtime.identifiers import require_identifier
from core.runtime.knowledge_providers.local_files import (
    enrich_local_files,
    register_local_files,
)
from core.workflow.config.bundle import KnowledgeBinding, TaskBundle
from core.workflow.config.lists import (
    merge_list_declarations,
    resolve_list,
)
from core.workflow.config.loader import load_workflow
from core.workflow.main import peek_capability_ids
from core.workflow.persistence.config_fingerprint import (
    assert_runtime_config_matches,
    write_runtime_config,
)
from harness.tools.lca_artifacts import checks as lca_checks
from harness.tools.lca_artifacts.bootstrap import lca_capabilities
from harness.tools.lca_artifacts.store import Context


def compose_capabilities(ids=None):
    ids = list(ids or [])
    if not ids:
        return base_capabilities()
    if ids == ["lca"] or all(
        str(i).startswith("lca") or str(i) == "lca_rework" for i in ids
    ):
        from harness.tools.lca_artifacts.bootstrap import lca_capabilities

        return lca_capabilities()
    raise ValueError(f"unknown capability set(s): {ids}")


from tests.conftest import PROJECT_ROOT, WORKFLOWS


def _generic_caps():
    caps = empty_capabilities()
    register_local_files(caps.knowledge)
    return caps


def _tree(root: Path) -> None:
    specs = root / "harness" / "specs" / "s1"
    specs.mkdir(parents=True)
    (specs / "README.md").write_text("# stage\n", encoding="utf-8")
    (specs / "executor.md").write_text("role=executor\n", encoding="utf-8")
    (specs / "reviewer.md").write_text("role=reviewer\n", encoding="utf-8")
    rules = root / "harness" / "rules" / "project"
    rules.mkdir(parents=True)
    for name in ("write-boundary.md", "runtime.md", "paths.md", "extra.md"):
        (rules / name).write_text(f"# {name}\n", encoding="utf-8")
    runtime = root / "harness" / "specs" / "public" / "references"
    runtime.mkdir(parents=True)
    (runtime / "workflow-runtime-spec.md").write_text("# runtime\n", encoding="utf-8")
    tools = root / "harness" / "tools" / "lca_artifacts"
    tools.mkdir(parents=True)
    (tools / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "harness").mkdir(parents=True, exist_ok=True)
    (root / "harness" / "knowledge").mkdir(parents=True)
    (root / "custom_docs").mkdir(parents=True)


def _reviewed_payload() -> dict:
    return {
        "id": "boundary",
        "runtime_spec": "harness/specs/public/references/workflow-runtime-spec.md",
        "registry": {
            "rules": {
                "workspace_boundary": "harness/rules/project/write-boundary.md",
                "runtime": "harness/rules/project/runtime.md",
                "paths": "harness/rules/project/paths.md",
                "extra_rule": "harness/rules/project/extra.md",
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
                "context": {"lca": {"phase": "mapping"}},
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


class MetadataIsolationTests(unittest.TestCase):
    def test_run_context_has_metadata_not_lca_phase(self) -> None:
        from dataclasses import fields

        names = {item.name for item in fields(RunContext)}
        self.assertIn("metadata", names)
        self.assertNotIn("lca_phase", names)

    def test_session_bind_uses_stage_context_not_checker_prefix(self) -> None:
        import inspect

        from core.workflow.execution import session_bind

        source = inspect.getsource(session_bind)
        self.assertNotIn('startswith("lca.")', source)
        self.assertNotIn("lca_phase", source)

    def test_phase_from_stage_context_independent_of_checker_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _reviewed_payload()
            payload["stages"][0]["checks"] = [
                {"id": "lca.report"},
                {"id": "lca.mapping"},
            ]
            payload["stages"][0]["context"] = {"lca": {"phase": "mapping"}}
            path = root / "harness" / "t.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=lca_capabilities()
            )
            bundle = workflow.bundles["s1.executor"]
            lca_meta = bundle.context.get("lca")
            self.assertIsInstance(lca_meta, dict)
            assert isinstance(lca_meta, dict)
            self.assertEqual(lca_meta.get("phase"), "mapping")
            self.assertEqual(bundle.checks[0].checker_id, "lca.report")


class AcceptanceSnapshotTests(unittest.TestCase):
    def test_report_extra_knowledge_does_not_stale_mapping_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "inputs").mkdir()
            (workspace / "inputs" / "plan.md").write_text("# plan\n", encoding="utf-8")
            (root / "custom_docs").mkdir(parents=True, exist_ok=True)
            (root / "custom_docs" / "product.txt").write_text("p\n", encoding="utf-8")
            (root / "report_docs").mkdir()
            (root / "report_docs" / "guide.txt").write_text("g\n", encoding="utf-8")

            mapping = Context(
                root,
                workspace,
                "run-1",
                "map",
                1,
                "reviewer",
                "map.reviewer",
                {"lca": {"phase": "mapping"}},
            )
            # Bind mapping knowledge into source manifest.
            m_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="run-1",
                stage_id="map",
                assignment_id="map.reviewer",
                attempt=1,
                role="reviewer",
                metadata={"lca": {"phase": "mapping"}},
            )
            enrich_local_files(
                m_ctx,
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
            mapping.manifest.parent.mkdir(parents=True, exist_ok=True)
            mapping.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-1", "calls": []}),
                encoding="utf-8",
            )
            inputs = lca_checks.dependencies(mapping, "mapping")
            check_path = lca_checks.check_path(mapping, "mapping")
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
                        "stage": mapping.stage,
                        "assignment": mapping.assignment,
                        "attempt": mapping.attempt,
                    }
                ),
                encoding="utf-8",
            )
            lca_checks.record_acceptance(mapping)

            report = Context(
                root,
                workspace,
                "run-1",
                "report",
                1,
                "executor",
                "report.executor",
                {"lca": {"phase": "report"}},
            )
            r_ctx = RunContext(
                project_root=root,
                workspace_root=workspace,
                run_id="run-1",
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
                            "custom_docs", "local_dir", "custom_docs/", "local_files"
                        ),
                        KnowledgeBinding(
                            "report_docs", "local_dir", "report_docs/", "local_files"
                        ),
                    ],
                ),
            )
            # Extra report knowledge must not invalidate frozen mapping acceptance.
            lca_checks.require_approved_model(report)

            (root / "custom_docs" / "product.txt").write_text(
                "changed\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                lca_checks.require_approved_model(report)

    def test_writer_reviewer_knowledge_difference_does_not_false_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "inputs").mkdir()
            (workspace / "inputs" / "plan.md").write_text("# plan\n", encoding="utf-8")
            (root / "a.md").write_text("source\n", encoding="utf-8")
            bom = workspace / "outputs" / "inventory" / "extracted-bom.json"
            bom.parent.mkdir(parents=True)
            row = {
                "item_id": "one",
                "name": "物料",
                "quantity": 1,
                "unit": "kg",
                "process": "制造",
                "transport": None,
                "geography": "CN",
                "source_locations": ["a.md#L1"],
                "extraction_status": "extracted",
            }
            bom.write_text(json.dumps({"items": [row]}), encoding="utf-8")
            (bom.parent / "extracted-bom.md").write_text("| x |\n", encoding="utf-8")
            writer = Context(
                root,
                workspace,
                "run-2",
                "inv",
                1,
                "executor",
                "inv.executor",
                {"lca": {"phase": "inventory"}},
            )
            writer.manifest.parent.mkdir(parents=True, exist_ok=True)
            writer.manifest.write_text(
                json.dumps({"accepted": {}, "run_id": "run-2", "calls": []}),
                encoding="utf-8",
            )
            sources = writer.sources_manifest_path()
            sources.parent.mkdir(parents=True, exist_ok=True)
            sources.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "a.md",
                                "readable": True,
                                "sha256": "0",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = lca_checks.validate(writer, "inventory")
            self.assertTrue(result["ok"])
            reviewer = Context(
                root,
                workspace,
                "run-2",
                "inv",
                1,
                "reviewer",
                "inv.reviewer",
                {"lca": {"phase": "inventory"}},
            )
            # Different assignment (and empty knowledge) must not mark frozen check stale.
            state = lca_checks.validation_state(reviewer, "inventory")
            self.assertEqual(state["status"], "passed")


class ReuseSeqTests(unittest.TestCase):
    def test_patch_chain_preserves_defaults(self) -> None:
        merged = merge_list_declarations(
            {"add": ["base_rule"]}, {"add": ["overlay_rule"]}
        )
        resolved = resolve_list(["default_rule"], merged)
        self.assertEqual(resolved, ["default_rule", "base_rule", "overlay_rule"])

    def test_plain_list_truncates_chain(self) -> None:
        merged = merge_list_declarations({"add": ["base_rule"]}, ["only"])
        self.assertEqual(resolve_list(["default_rule"], merged), ["only"])

    def test_empty_list_clears(self) -> None:
        self.assertEqual(resolve_list(["a", "b"], []), [])

    def test_base_and_overlay_assignment_patch_via_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            base = _reviewed_payload()
            base["defaults"]["rules"] = ["workspace_boundary", "runtime", "paths"]
            base["assignments"]["s1.executor"]["rules"] = {"add": ["extra_rule"]}
            base_path = root / "harness" / "base.yaml"
            base_path.write_text(
                yaml.safe_dump(base, allow_unicode=True), encoding="utf-8"
            )
            overlay = {
                "id": "overlay",
                "reuse": "harness/base.yaml",
                "assignments": {
                    "s1.executor": {
                        "role": "executor",
                        "task_spec": "harness/specs/s1/executor.md",
                        "tools": ["lca_artifacts"],
                        "rules": {"add": ["paths"], "remove": ["runtime"]},
                    }
                },
            }
            # After base patch removed nothing yet; overlay removes runtime and re-adds paths.
            # Wait: base already has paths from defaults; remove runtime; add paths (noop).
            path = root / "harness" / "overlay.yaml"
            path.write_text(
                yaml.safe_dump(overlay, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=_generic_caps()
            )
            rules = workflow.bundles["s1.executor"].rule_ids
            self.assertIn("workspace_boundary", rules)
            self.assertIn("extra_rule", rules)
            self.assertNotIn("runtime", rules)
            self.assertIn("paths", rules)


class TopologyAndIdTests(unittest.TestCase):
    def test_two_writers_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _reviewed_payload()
            payload["assignments"]["s1.reviser"] = {
                "role": "reviser",
                "task_spec": "harness/specs/s1/executor.md",
                "tools": [],
            }
            payload["stages"][0]["steps"] = [
                {"assignment": "s1.executor"},
                {"assignment": "s1.reviser"},
            ]
            path = root / "harness" / "bad.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=_generic_caps())

    def test_reviewer_before_writer_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _tree(root)
            payload = _reviewed_payload()
            payload["stages"][0]["steps"] = [
                {"assignment": "s1.reviewer"},
                {"assignment": "s1.executor"},
            ]
            path = root / "harness" / "bad.yaml"
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=_generic_caps())

    def test_illegal_assignment_id(self) -> None:
        with self.assertRaises(ValueError):
            require_identifier("../foo", label="assignment id")
        with self.assertRaises(ValueError):
            require_identifier("a/b", label="assignment id")
        self.assertEqual(
            require_identifier("lca.report", label="checker id"), "lca.report"
        )


class CapabilitiesAndResumeTests(unittest.TestCase):
    def test_empty_capabilities_compose(self) -> None:
        caps = compose_capabilities([])
        self.assertIn("local_files", caps.knowledge.known_ids())
        self.assertEqual(set(caps.checkers.known_ids()), set())

    def test_unknown_capability_fail(self) -> None:
        with self.assertRaises(ValueError):
            compose_capabilities(["nope"])

    def test_peek_lca_from_main(self) -> None:
        ids = peek_capability_ids(
            WORKFLOWS / "LCA-main.yaml", project_root=PROJECT_ROOT
        )
        self.assertEqual(
            set(ids),
            {
                "lca.inventory",
                "lca.mapping",
                "lca.report",
                "lca.record_acceptance",
                "lca_rework",
            },
        )

    def test_resume_fingerprint_mismatch(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_runtime_config(
                workspace,
                "run-x",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="test-model",
            )
            assert_runtime_config_matches(
                workspace,
                "run-x",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="test-model",
            )
            # Mutate a live rule file hash by writing a different fingerprint file.
            stored = json.loads(
                (
                    workspace / "memory" / "evidence" / "run-x" / "runtime-config.json"
                ).read_text(encoding="utf-8")
            )
            stored["fingerprint"] = "tampered"
            (
                workspace / "memory" / "evidence" / "run-x" / "runtime-config.json"
            ).write_text(json.dumps(stored), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "configuration changed"):
                assert_runtime_config_matches(
                    workspace,
                    "run-x",
                    workflow,
                    project_root=PROJECT_ROOT,
                    worker="codex",
                    model="test-model",
                )


class ArchiveIdentityTests(unittest.TestCase):
    def test_archive_and_render_use_assignment_id(self) -> None:
        from core.agents.archive import mcp_render_dir, turn_archive_dir

        root = Path("/tmp/ws")
        self.assertEqual(
            mcp_render_dir(root, "r", "s", "s.executor"),
            root / "tmp" / "mcp-render" / "r" / "s" / "s.executor",
        )
        self.assertEqual(
            turn_archive_dir(root, "r", "s", "s.executor", 2),
            root / "memory" / "logs" / "r" / "s" / "s.executor#2",
        )


if __name__ == "__main__":
    unittest.main()
