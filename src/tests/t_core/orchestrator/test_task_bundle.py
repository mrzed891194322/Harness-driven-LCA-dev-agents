from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from core.runtime.capabilities import base_capabilities
from core.workflow.config.loader import load_workflow
from core.workflow.config.resolve import diagnose_assignment
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.minimal_workflow import write_minimal_workflow


class TaskBundleResolveTests(unittest.TestCase):
    def test_whole_lca_has_seven_bundles(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        self.assertEqual(len(workflow.bundles), 7)
        executor = workflow.bundles["03-dataset-mapping.executor"]
        self.assertEqual(executor.mcp_tool_ids, ["control_openlca", "lca_artifacts"])
        self.assertIn("openlca_usage", executor.rule_ids)
        self.assertIn("workspace_knowledge", executor.knowledge_ids)
        self.assertEqual(
            executor.stage_spec.source_path,
            "harness/specs/03-dataset-mapping/spec.yaml",
        )
        self.assertEqual(executor.acceptance_checks[0].id, "mapping")
        self.assertEqual(executor.acceptance_checks[0].action, "mapping_check")

    def test_writer_outputs_and_checks(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
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
        self.assertEqual(writer.acceptance_checks[0].action, "inventory_check")
        self.assertEqual(writer.acceptance_checks[0].arguments, {})
        self.assertEqual(reviewer.expected_outputs, [])
        self.assertEqual(reviewer.acceptance_checks[0].id, "inventory")

    def test_revise_independent_bundles(self) -> None:
        revise = load_workflow(
            WORKFLOWS / "LCA-revise.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        reviser = revise.bundles["03-dataset-mapping.reviser"]
        reviewer = revise.bundles["03-dataset-mapping.reviewer"]
        self.assertEqual(reviser.role, "reviser")
        self.assertIn("lca_method", reviser.rule_ids)
        self.assertIn("stage_03_revise", reviser.rule_ids)
        self.assertIn("reviewer_readonly", reviewer.rule_ids)
        self.assertIn("lca_method", reviewer.rule_ids)
        intake = revise.stage_by_id("01-intake-gate")
        self.assertEqual(intake.steps, ["01-intake-gate.reviewer"])
        self.assertIn("stage_01_revise", revise.bundles[intake.steps[0]].rule_ids)

    def test_diagnose_assignment_keys(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
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
                "spec",
                "rules",
                "tools",
                "knowledge",
                "outputs",
                "acceptance_checks",
                "on_reviewer_passed",
            },
        )

    def test_list_patch_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_path = write_minimal_workflow(root)
            workflow = load_workflow(
                workflow_path, project_root=root, capabilities=base_capabilities()
            )
            bundle = workflow.bundles["s1.executor"]
            self.assertIn("extra_rule", bundle.rule_ids)
            self.assertNotIn("paths", bundle.rule_ids)

    def test_fail_fast_unknown_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_path = write_minimal_workflow(root)
            payload = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
            payload["assignments"]["s1.executor"]["tools"] = {"mcp": ["missing_tool"]}
            workflow_path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_workflow(
                    workflow_path, project_root=root, capabilities=base_capabilities()
                )

    def test_fail_fast_unknown_acceptance_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_path = write_minimal_workflow(
                root,
                acceptance=[
                    {
                        "id": "bad",
                        "action": "missing_action",
                        "arguments": {},
                    }
                ],
            )
            with self.assertRaises(ValueError):
                load_workflow(
                    workflow_path, project_root=root, capabilities=base_capabilities()
                )

    def test_bundle_round_trip_dict(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        bundle = workflow.bundles["02-inventory-extraction.executor"]
        payload = bundle.to_dict()
        self.assertEqual(payload["assignment_id"], bundle.assignment_id)
        self.assertEqual(payload["expected_outputs"], bundle.expected_outputs)
        self.assertEqual(payload["stage_spec_path"], bundle.stage_spec.source_path)
        self.assertEqual(
            payload["acceptance_checks"][0]["id"], bundle.acceptance_checks[0].id
        )


if __name__ == "__main__":
    unittest.main()
