from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
SPEC_ROOT = PROJECT_ROOT / "harness" / "specs"

STAGE_EXPECTATIONS = {
    "01-plan-quality-gate": (
        "validate_plan_intake",
        "review.schema.json",
        "src/GUI/ui/assets/template/plan.md",
    ),
    "02-evidence-retrieval": (
        "list_rag_libraries",
        "query_rag",
        "query_descriptors",
        "get_process_details",
        "get_flow_providers",
    ),
    "03-lci-construction": (
        "workspace/outputs/LCI",
        "references/scripts/validation.py",
        "一文件一实体",
    ),
    "04-lci-quality-evaluation": (
        "next_lci_review_action",
        "review.schema.json",
    ),
    "05-openlca-preflight-confirmation": (
        "preflight_import_lci",
        "没有独立文件型 JSON Schema",
    ),
    "06-openlca-import-readback": (
        "import_lci",
        "get_import_operation",
        "get_model_graph",
        "references/schemas/import-report.schema.json",
        "references/schemas/import-operation-status.schema.json",
        "references/schemas/model-graph.schema.json",
        "references/scripts/validation.py",
    ),
    "07-lcia-calculation-reporting": (
        "calculate_product_system",
        "references/schemas/raw-lcia-results.schema.json",
        "references/schemas/calculation-manifest.schema.json",
        "references/templates/lca_report.md",
        "references/scripts/validation.py",
    ),
}

EXPECTED_SOURCE_PATHS = (
    "src/GUI/ui/assets/template/plan.md",
    "harness/rules/knowledge-retrieval/README.md",
    "harness/rules/openlca-operation/README.md",
    "harness/specs/public/references/handshake-common.md",
    "harness/specs/public/references/workflow-runtime-spec.md",
    "harness/specs/public/references/schemas/common.schema.json",
    "harness/specs/public/references/schemas/workflow-manifest.schema.json",
    "harness/specs/public/references/schemas/stage.schema.json",
    "harness/specs/public/references/schemas/review.schema.json",
    "harness/specs/public/references/schemas/handoff.schema.json",
    "harness/specs/01-plan-quality-gate/references/scripts/validation.py",
    "harness/specs/03-lci-construction/references/scripts/validation.py",
    "harness/specs/04-lci-quality-evaluation/references/scripts/validation.py",
    "harness/specs/06-openlca-import-readback/references/schemas/import-report.schema.json",
    "harness/specs/06-openlca-import-readback/references/schemas/import-operation-status.schema.json",
    "harness/specs/06-openlca-import-readback/references/schemas/model-graph.schema.json",
    "harness/specs/06-openlca-import-readback/references/scripts/validation.py",
    "harness/specs/07-lcia-calculation-reporting/references/schemas/raw-lcia-results.schema.json",
    "harness/specs/07-lcia-calculation-reporting/references/schemas/calculation-manifest.schema.json",
    "harness/specs/07-lcia-calculation-reporting/references/templates/lca_report.md",
    "harness/specs/07-lcia-calculation-reporting/references/scripts/validation.py",
)


class StageSchemaMappingTests(unittest.TestCase):
    def test_each_stage_routes_a_mermaid_and_table_mapping(self) -> None:
        for stage, expected_tokens in STAGE_EXPECTATIONS.items():
            stage_root = SPEC_ROOT / stage
            mapping_path = stage_root / "schema_mapping.md"
            self.assertTrue(mapping_path.is_file(), stage)

            readme = (stage_root / "README.md").read_text(encoding="utf-8")
            self.assertIn("schema_mapping.md", readme, stage)

            mapping = mapping_path.read_text(encoding="utf-8")
            self.assertIn("```mermaid", mapping, stage)
            self.assertIn("| 类型 |", mapping, stage)
            self.assertIn("handshake-common.md", mapping, stage)
            for token in expected_tokens:
                self.assertIn(token, mapping, f"{stage}: {token}")

    def test_all_file_backed_mapping_contracts_exist(self) -> None:
        for relative_path in EXPECTED_SOURCE_PATHS:
            self.assertTrue((PROJECT_ROOT / relative_path).is_file(), relative_path)

    def test_stage_only_assets_are_not_kept_in_public(self) -> None:
        public_references = SPEC_ROOT / "public" / "references"
        for relative_path in (
            "scripts/validation.py",
            "schemas/import-report.schema.json",
            "schemas/import-operation-status.schema.json",
            "schemas/model-graph.schema.json",
            "schemas/raw-lcia-results.schema.json",
            "schemas/calculation-manifest.schema.json",
            "templates/lca_report.md",
        ):
            self.assertFalse((public_references / relative_path).exists(), relative_path)

    def test_workflow_adapters_route_stage_local_contracts(self) -> None:
        adapter_content = (
            PROJECT_ROOT / "harness/workflows/LCA-main.md"
        ).read_text(encoding="utf-8")
        for relative_path in (
            "harness/specs/06-openlca-import-readback/references/schemas/import-report.schema.json",
            "harness/specs/06-openlca-import-readback/references/schemas/import-operation-status.schema.json",
            "harness/specs/06-openlca-import-readback/references/schemas/model-graph.schema.json",
            "harness/specs/07-lcia-calculation-reporting/references/schemas/raw-lcia-results.schema.json",
            "harness/specs/07-lcia-calculation-reporting/references/schemas/calculation-manifest.schema.json",
            "harness/specs/07-lcia-calculation-reporting/references/templates/lca_report.md",
        ):
            self.assertIn(relative_path, adapter_content, relative_path)
        self.assertNotIn("harness/specs/public/references/templates/", adapter_content)
        self.assertNotIn(
            "harness/specs/public/references/schemas/import-report",
            adapter_content,
        )

    def test_common_artifact_schema_is_shared(self) -> None:
        schema_dir = SPEC_ROOT / "public" / "references" / "schemas"
        common = json.loads((schema_dir / "common.schema.json").read_text(encoding="utf-8"))
        required = set(common["$defs"]["artifact"]["required"])
        for schema_name in (
            "workflow-manifest.schema.json",
            "handoff.schema.json",
            "review.schema.json",
        ):
            schema = json.loads((schema_dir / schema_name).read_text(encoding="utf-8"))
            self.assertNotIn("artifact", schema.get("$defs", {}), schema_name)
        revise_manifest = json.loads(
            (
                SPEC_ROOT
                / "08-lca-revise-workflow"
                / "references"
                / "schemas"
                / "workflow-manifest.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(required, {"artifact_id", "kind", "path"})
        self.assertIn(
            "whole-lca/common.schema.json#/$defs/artifact",
            json.dumps(revise_manifest),
        )


if __name__ == "__main__":
    unittest.main()
