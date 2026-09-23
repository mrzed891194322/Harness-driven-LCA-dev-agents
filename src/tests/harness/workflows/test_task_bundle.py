from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.workflows.domains.lca.bootstrap import lca_capabilities
from scripts.workflows.orchestrator.load.loader import load_workflow
from scripts.workflows.orchestrator.load.resolve import diagnose_assignment
from tests.conftest import PROJECT_ROOT, WORKFLOWS

STAGE_PACKAGES = (
    "01-intake-gate",
    "02-inventory-extraction",
    "03-dataset-mapping",
    "04-openlca-reporting",
)


class TaskBundleResolveTests(unittest.TestCase):
    def test_whole_lca_has_seven_bundles(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        self.assertEqual(len(workflow.bundles), 7)
        executor = workflow.bundles["03-dataset-mapping.executor"]
        self.assertEqual(executor.tool_ids, ["control_openlca", "lca_artifacts"])
        self.assertIn("openlca_usage", executor.rule_ids)
        self.assertIn("workspace_knowledge", executor.knowledge_ids)
        self.assertEqual(executor.spec_paths[0], workflow.runtime_spec)
        self.assertEqual(
            executor.spec_paths[-1],
            workflow.assignments["03-dataset-mapping.executor"].task_spec,
        )

    def test_writer_outputs_and_checks(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        writer = workflow.bundles["02-inventory-extraction.executor"]
        reviewer = workflow.bundles["02-inventory-extraction.reviewer"]
        self.assertEqual(
            writer.expected_outputs,
            [
                "workspace/outputs/inventory/extracted-bom.json",
                "workspace/outputs/inventory/extracted-bom.md",
            ],
        )
        self.assertEqual(writer.checks[0].checker_id, "lca.inventory")
        self.assertEqual(reviewer.expected_outputs, [])
        self.assertEqual(reviewer.checks[0].checker_id, "lca.inventory")

    def test_revise_overlay_bundles(self) -> None:
        revise = load_workflow(
            WORKFLOWS / "LCA-revise.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        reviser = revise.bundles["03-dataset-mapping.reviser"]
        reviewer = revise.bundles["03-dataset-mapping.reviewer"]
        self.assertEqual(reviser.role, "reviser")
        self.assertIn("lca_method", reviser.rule_ids)
        self.assertIn("reviewer_readonly", reviewer.rule_ids)
        self.assertIn("lca_method", reviewer.rule_ids)
        intake = revise.stage_by_id("01-intake-gate")
        self.assertTrue(
            any(item.endswith("references/revise.md") for item in intake.spec_additions)
        )
        self.assertEqual(intake.steps, ["01-intake-gate.reviewer"])

    def test_diagnose_assignment_keys(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        payload = diagnose_assignment(
            workflow, "03-dataset-mapping", "03-dataset-mapping.executor"
        )
        self.assertEqual(
            set(payload.keys()),
            {
                "assignment_id",
                "stage_id",
                "role",
                "specs",
                "rules",
                "tools",
                "knowledge",
                "outputs",
                "checks",
                "reviewer_passed_hooks",
            },
        )

    def test_list_patch_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            knowledge_dir = root / "harness" / "knowledge"
            knowledge_dir.mkdir(parents=True)
            (knowledge_dir / "README.md").write_text("# k\n", encoding="utf-8")
            _write_minimal_workflow(root)
            workflow_path = root / "harness" / "patch-test.yaml"
            workflow = load_workflow(
                workflow_path, project_root=root, capabilities=lca_capabilities()
            )
            bundle = workflow.bundles["s1.executor"]
            self.assertIn("extra_rule", bundle.rule_ids)
            self.assertNotIn("paths", bundle.rule_ids)

    def test_fail_fast_unknown_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            knowledge_dir = root / "harness" / "knowledge"
            knowledge_dir.mkdir(parents=True)
            (knowledge_dir / "README.md").write_text("# k\n", encoding="utf-8")
            _write_minimal_workflow(root)
            workflow_path = root / "harness" / "patch-test.yaml"
            payload = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
            payload["assignments"]["s1.executor"]["tools"] = ["missing_tool"]
            workflow_path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(
                    workflow_path, project_root=root, capabilities=lca_capabilities()
                )

    def test_fail_fast_invalid_checker_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            knowledge_dir = root / "harness" / "knowledge"
            knowledge_dir.mkdir(parents=True)
            (knowledge_dir / "README.md").write_text("# k\n", encoding="utf-8")
            _write_minimal_workflow(root)
            workflow_path = root / "harness" / "patch-test.yaml"
            text = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
            text["stages"][0]["checks"] = [{"id": "not-a-checker"}]
            workflow_path.write_text(
                yaml.safe_dump(text, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(
                    workflow_path, project_root=root, capabilities=lca_capabilities()
                )

    def test_bundle_round_trip(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        bundle = workflow.bundles["02-inventory-extraction.executor"]
        from scripts.workflows.orchestrator.load.bundle import TaskBundle

        restored = TaskBundle.from_dict(bundle.to_dict())
        self.assertEqual(restored.assignment_id, bundle.assignment_id)
        self.assertEqual(restored.expected_outputs, bundle.expected_outputs)


def _write_minimal_workflow(root: Path) -> None:
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
    workflows = root / "harness"
    workflows.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": "patch-test",
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
                }
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
                "outputs": ["workspace/out.txt"],
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
                "rules": {"add": ["extra_rule"], "remove": ["paths"]},
            },
            "s1.reviewer": {
                "role": "reviewer",
                "task_spec": "harness/specs/s1/reviewer.md",
                "tools": [],
            },
        },
    }
    (workflows / "patch-test.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
    )


if __name__ == "__main__":
    unittest.main()
