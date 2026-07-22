from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from validation import next_lci_review_action, validate_plan_intake


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
SPEC_ROOT = SCRIPT_ROOT.parent
SCHEMA_ROOT = SPEC_ROOT / "schemas"
TIMESTAMP = "2026-07-22T08:00:00Z"
HASH = "a" * 64
RUN_ID = "20260722T080000Z-deadbeef"


def compliant_plan(extra: str = "", version: str = "1", functional_unit: str = "1 kg bottled product") -> str:
    return f"""---
template_kind: lca_execution_plan
template_version: {version}
---

# LCA 项目执行计划

## 1. 研究目的与范围定义
- **研究对象**：标准包装产品
- **研究目的**：识别从原料到工厂大门的环境热点，用于内部改进
- **功能单位 (FU)**：{functional_unit}
- **生命周期阶段**：Cradle-to-Gate，包含原料、运输和制造
- **质量/能量截断比例**：不采用自动截断，所有已知输入均纳入
- **多产出分配**：无副产品；不适用分配

## 2. 生命周期影响评价方法与指标
使用活动数据库中可检索的方法。

## 3. openLCA 环境与数据基础
使用本地 IPC 活动数据库。

## 4. openLCA 模型细节方案
创建前景 Flow、Process 和 Product System。

## 5. 结果的验证与解释方案
以无断链、非空 LCIA 结果和结果文件通过契约作为完成判断。

## 6. 待完善清单
{extra}
"""


class PlanIntakeTests(unittest.TestCase):
    def test_compliant_plan_passes(self) -> None:
        result = validate_plan_intake(compliant_plan())
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["issues"], [])

    def test_explicit_retrievable_gap_is_allowed(self) -> None:
        gap = """- GAP-METHOD
  - gap_type: retrievable
  - retrieval_target: 活动数据库中的 LCIA 方法名称与 UUID
  - source_domain: openlca
"""
        result = validate_plan_intake(compliant_plan(extra=gap))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["retrievable_gaps"], ["GAP-METHOD"])

    def test_missing_functional_unit_blocks(self) -> None:
        result = validate_plan_intake(
            compliant_plan(functional_unit="[请填写功能单位]")
        )
        self.assertEqual(result["status"], "needs_input")
        self.assertIn("PLAN-BLOCKING-FU", {issue["issue_id"] for issue in result["issues"]})

    def test_unknown_template_version_blocks(self) -> None:
        result = validate_plan_intake(compliant_plan(version="99"))
        self.assertEqual(result["status"], "needs_input")
        self.assertIn("PLAN-FORMAT-VERSION", {issue["issue_id"] for issue in result["issues"]})


class ReviewLoopTests(unittest.TestCase):
    def test_first_two_failures_fix_and_third_failure_stops(self) -> None:
        self.assertEqual(next_lci_review_action(1, False), "targeted_fix_and_review")
        self.assertEqual(next_lci_review_action(2, False), "targeted_fix_and_review")
        self.assertEqual(next_lci_review_action(3, False), "stop_needs_review")
        self.assertEqual(next_lci_review_action(2, True), "proceed_to_preflight")
        with self.assertRaises(ValueError):
            next_lci_review_action(4, False)


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas: dict[str, dict] = {}
        registry = Registry()
        for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            cls.schemas[path.name] = schema
            registry = registry.with_resource(
                schema["$id"], Resource.from_contents(schema)
            )
        cls.registry = registry

    def validate(self, schema_name: str, instance: dict) -> None:
        validator = Draft202012Validator(
            self.schemas[schema_name],
            registry=self.registry,
            format_checker=FormatChecker(),
        )
        validator.validate(instance)

    def artifact(self, artifact_id: str = "artifact:plan") -> dict:
        return {
            "artifact_id": artifact_id,
            "kind": "plan",
            "path": "workspace/plan/execution_plan.md",
            "sha256": HASH,
            "source_artifact_ids": [],
            "revision_of": None,
        }

    def test_positive_manifest_stage_review_and_handoff(self) -> None:
        manifest = {
            "schema": "whole-lca/workflow-manifest",
            "version": "1.0",
            "run_id": RUN_ID,
            "platform": "codex",
            "orchestrator_agent": "major-orchestrator",
            "plan": self.artifact(),
            "started_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "status": "running",
            "current_stage": "plan-review",
            "preflight_hash": None,
            "lci_review_attempt": 0,
            "artifact_index": [self.artifact()],
            "issue_ids": [],
        }
        stage = {
            "schema": "whole-lca/stage",
            "version": "1.0",
            "run_id": RUN_ID,
            "stage_id": "stage-001-plan-review",
            "supersedes_stage_id": None,
            "sequence": 1,
            "stage": "plan-review",
            "agent": "eval-reviewer",
            "started_at": TIMESTAMP,
            "ended_at": TIMESTAMP,
            "status": "passed",
            "artifact_ids": ["artifact:plan"],
            "evidence_refs": ["reviews/plan-review.json"],
            "issue_ids": [],
            "summary": "Plan passed intake.",
        }
        review = {
            "schema": "whole-lca/review",
            "version": "1.0",
            "run_id": RUN_ID,
            "review_id": "review-plan",
            "supersedes_review_id": None,
            "review_type": "plan",
            "attempt": 1,
            "reviewer": "eval-reviewer",
            "timestamp": TIMESTAMP,
            "status": "passed",
            "reviewed_artifacts": [self.artifact()],
            "issues": [],
            "retrievable_gaps": ["GAP-METHOD"],
            "summary": "Plan can proceed.",
        }
        handoff = {
            "schema": "whole-lca/handoff",
            "version": "1.0",
            "run_id": RUN_ID,
            "handoff_id": "handoff-001-plan-review",
            "supersedes_handoff_id": None,
            "stage_id": "stage-001-plan-review",
            "from_agent": "major-orchestrator",
            "to_agent": "eval-reviewer",
            "timestamp": TIMESTAMP,
            "input_artifacts": [self.artifact()],
            "decision": "Review plan intake.",
            "evidence_refs": ["workspace/plan/execution_plan.md"],
            "unresolved_items": [],
            "status": "completed",
            "next_action": "Retrieve evidence.",
            "issue_ids": [],
        }
        self.validate("workflow-manifest.schema.json", manifest)
        self.validate("stage.schema.json", stage)
        self.validate("review.schema.json", review)
        self.validate("handoff.schema.json", handoff)

    def test_positive_import_graph_raw_and_calculation_manifests(self) -> None:
        entity_ref = {"id": "11111111-1111-4111-8111-111111111111", "name": "PS1 Test"}
        import_report = {
            "schema": "whole-lca/import-report",
            "version": "1.0",
            "operation_id": "11111111-1111-4111-8111-111111111111",
            "status": "success",
            "endpoint": "http://localhost:8080",
            "active_database": "isolated-db",
            "target_category": "test-project",
            "preflight_hash": HASH,
            "started_at": TIMESTAMP,
            "ended_at": TIMESTAMP,
            "duration_ms": 10,
            "success_count": 1,
            "failed_count": 0,
            "deleted_count": 0,
            "entities": [{"path": "flows/f01.json", "entity_type": "Flow", "id": entity_ref["id"], "name": "F01 Test", "action": "create_or_update", "status": "success", "error": None}],
            "errors": [],
        }
        graph = {
            "schema": "whole-lca/model-graph",
            "version": "1.0",
            "status": "success",
            "endpoint": "http://localhost:8080",
            "product_system": entity_ref,
            "nodes": [{"id": "p1", "name": "P1"}],
            "edges": [],
            "broken_links": [],
            "disconnected_nodes": [],
            "timestamp": TIMESTAMP,
            "error": None,
        }
        raw = {
            "schema": "whole-lca/raw-lcia-results",
            "version": "1.0",
            "status": "success",
            "endpoint": "http://localhost:8080",
            "product_system": entity_ref,
            "impact_method": {"id": "method-id", "name": "EF"},
            "calculation_setup": {"amount": 1.0},
            "impact_categories": [{"name": "Climate change", "id": "impact-id", "amount": 1.25, "unit": "kg CO2-eq"}],
            "resource_released": True,
            "started_at": TIMESTAMP,
            "ended_at": TIMESTAMP,
            "error": None,
        }
        calculation = {
            "schema": "whole-lca/calculation-manifest",
            "version": "1.0",
            "run_id": RUN_ID,
            "status": "success",
            "active_database": "isolated-db",
            "product_system": entity_ref,
            "impact_method": {"id": "method-id", "name": "EF"},
            "functional_unit_amount": 1.0,
            "allocation": None,
            "regionalized": False,
            "costs": False,
            "parameters": {},
            "tool_versions": {"olca-ipc": "2.0"},
            "calculated_at": TIMESTAMP,
            "raw_result": {"path": "workspace/results/run/raw/ps1.json", "sha256": HASH},
            "resource_released": True,
            "unresolved_items": [],
        }
        self.validate("import-report.schema.json", import_report)
        self.validate("model-graph.schema.json", graph)
        self.validate("raw-lcia-results.schema.json", raw)
        self.validate("calculation-manifest.schema.json", calculation)

    def test_negative_contract_examples_are_rejected(self) -> None:
        invalid_manifest = {
            "schema": "whole-lca/workflow-manifest",
            "version": "1.0",
            "run_id": RUN_ID,
            "platform": "codex",
            "orchestrator_agent": "major-orchestrator",
            "plan": self.artifact(),
            "started_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "status": "done",
            "lci_review_attempt": 4,
            "artifact_index": [],
        }
        with self.assertRaises(ValidationError):
            self.validate("workflow-manifest.schema.json", invalid_manifest)

    def test_report_template_contains_traceability_and_claim_boundary(self) -> None:
        template = (SPEC_ROOT / "templates" / "lca_report.md").read_text(encoding="utf-8")
        self.assertIn("raw_result_sha256", template)
        self.assertIn("原始结果位置", template)
        self.assertIn("不自动构成 ISO 认证", template)


if __name__ == "__main__":
    unittest.main()
