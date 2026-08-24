from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
SPEC_ROOT = SCRIPT_ROOT.parent
SCHEMA_ROOTS = (
    SPEC_ROOT / "schemas",
    PROJECT_ROOT
    / "harness"
    / "specs"
    / "06-openlca-import-readback"
    / "references"
    / "schemas",
    PROJECT_ROOT
    / "harness"
    / "specs"
    / "07-lcia-calculation-reporting"
    / "references"
    / "schemas",
)
TIMESTAMP = "2026-07-22T08:00:00Z"


def load_stage_validation(stage: str):
    path = (
        PROJECT_ROOT
        / "harness"
        / "specs"
        / stage
        / "references"
        / "scripts"
        / "validation.py"
    )
    spec = importlib.util.spec_from_file_location(f"{stage}_validation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load stage validation module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_validate_plan_intake = load_stage_validation(
    "01-plan-quality-gate"
).validate_plan_intake


def validate_plan_intake(text: str, *, reference_roots=()) -> dict:
    """Keep contract tests isolated from real runtime reference directories."""
    return _validate_plan_intake(text, reference_roots=reference_roots)


next_lci_review_action = load_stage_validation(
    "04-lci-quality-evaluation"
).next_lci_review_action


def compliant_plan(
    extra: str = "",
    functional_unit: str = "1 kg bottled product",
    front_matter: str = "",
) -> str:
    return f"""{front_matter}# LCA 项目执行计划

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

    def test_reference_inventory_includes_gitignored_runtime_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reference_root = Path(temp_dir) / "file"
            nested = reference_root / "sample-reference"
            nested.mkdir(parents=True)
            (reference_root / ".gitignore").write_text("*\n", encoding="utf-8")
            (reference_root / "README.md").write_text("control\n", encoding="utf-8")
            reference = nested / "sample-reference.md"
            reference.write_text("runtime evidence\n", encoding="utf-8")

            result = validate_plan_intake(
                compliant_plan(extra="使用参考资料 sample-reference.md"),
                reference_roots=(reference_root,),
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            result["reference_inventory"],
            {
                "roots": [reference_root.resolve().as_posix()],
                "files": [reference.resolve().as_posix()],
            },
        )
        self.assertNotIn(
            "PLAN-REFERENCE-NOT-LOCATED",
            {issue["issue_id"] for issue in result["issues"]},
        )

    def test_reference_inventory_records_empty_negative_lookup_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_root = Path(temp_dir) / "file"
            data_root = Path(temp_dir) / "data"

            result = validate_plan_intake(
                compliant_plan(extra="使用参考资料 absent-reference.md"),
                reference_roots=(file_root, data_root),
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["reference_inventory"]["files"], [])
        self.assertEqual(
            result["reference_inventory"]["roots"],
            sorted((file_root.resolve().as_posix(), data_root.resolve().as_posix())),
        )

    def test_explicit_retrievable_gap_is_optional_hint(self) -> None:
        gap = """- GAP-METHOD
  - gap_type: retrievable
  - retrieval_target: 活动数据库中的 LCIA 方法名称与 UUID
  - source_domain: openlca
"""
        result = validate_plan_intake(compliant_plan(extra=gap))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["retrievable_gaps"], ["GAP-METHOD"])

    def test_natural_language_retrieval_without_gap_ids_passes(self) -> None:
        extra = (
            "Agent 从该资料提取物料、质量、运输、地域和建模关系，"
            "并从活动数据库匹配背景数据。"
            "Agent 按项目 LCI 规范自行完成 Provider 映射。"
        )
        result = validate_plan_intake(compliant_plan(extra=extra))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["retrievable_gaps"], [])

    def test_bare_gap_token_is_hint_not_blocking(self) -> None:
        result = validate_plan_intake(compliant_plan(extra="请检索 GAP-METHOD"))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["retrievable_gaps"], ["GAP-METHOD"])
        self.assertFalse(
            any(issue["issue_id"].startswith("PLAN-GAP-") for issue in result["issues"])
        )

    def test_spec_forbids_blocking_on_missing_gap_tokens(self) -> None:
        spec = (
            PROJECT_ROOT
            / "harness"
            / "specs"
            / "01-plan-quality-gate"
            / "references"
            / "01-plan-quality-gate-spec.md"
        ).read_text(encoding="utf-8")
        self.assertIn("不要求出现 `GAP-*`", spec)
        self.assertIn("PLAN-RETRIEVABLE-GAPS-UNTRACKED", spec)
        self.assertIn("不得因此将审查置为 `failed`", spec)

    def test_missing_functional_unit_blocks(self) -> None:
        result = validate_plan_intake(
            compliant_plan(functional_unit="[请填写功能单位]")
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("PLAN-BLOCKING-FU", {issue["issue_id"] for issue in result["issues"]})
        issue = next(
            issue for issue in result["issues"] if issue["issue_id"] == "PLAN-BLOCKING-FU"
        )
        self.assertTrue(issue["spec_ref"].startswith("01-plan-quality-gate-spec.md#"))

    def test_missing_or_arbitrary_metadata_does_not_block(self) -> None:
        plans = (
            compliant_plan(),
            compliant_plan(
                front_matter=(
                    "---\n"
                    "template_kind: arbitrary\n"
                    "template_version: 99\n"
                    "custom_key: preserved\n"
                    "---\n\n"
                )
            ),
        )
        for plan in plans:
            result = validate_plan_intake(plan)
            self.assertEqual(result["status"], "passed")
            self.assertFalse(
                any(
                    issue["issue_id"].startswith("PLAN-FORMAT-")
                    for issue in result["issues"]
                )
            )

    def test_legacy_reference_path_does_not_block(self) -> None:
        plan = compliant_plan(
            extra="harness/knowledge/inputs/user_file/report.md",
        )
        result = validate_plan_intake(plan)
        self.assertEqual(result["status"], "passed")
        self.assertNotIn(
            "PLAN-REF-LEGACY-PATH",
            {issue["issue_id"] for issue in result["issues"]},
        )

    def test_semantic_plan_does_not_require_fixed_six_chapter_titles(self) -> None:
        plan = compliant_plan()
        plan = plan.replace("## 1. 研究目的与范围定义", "## 目标与范围")
        for section in range(2, 7):
            plan = plan.replace(f"## {section}.", f"### 自定义章节 {section}：")

        result = validate_plan_intake(plan)

        self.assertEqual(result["status"], "passed")
        self.assertFalse(
            any(issue["issue_id"].startswith("PLAN-SECTION-") for issue in result["issues"])
        )

    def test_gui_legacy_input_blocks_are_checked_semantically(self) -> None:
        def field(label: str, value: str) -> str:
            return (
                f"- **{label}**：\n"
                "  ---\n"
                "  ***✍️ 用户填写内容区***\n\n"
                f"  {value}\n\n"
                "  ---\n"
            )

        plan = (
            "---\n"
            "template_kind: lca_plan_input\n"
            "template_version: 1\n"
            "---\n\n"
            "# 自定义 GUI 计划\n\n"
            + field("研究主体", "标准包装产品")
            + field("功能单位（Functional Unit）", "1 kg bottled product")
            + field("评估目的与预期用途", "识别环境热点，用于内部改进")
            + field("系统边界（System Boundary）", "Cradle-to-Gate")
            + field(
                "范围定义与系统边界细化",
                "不采用自动截断；无副产品，不适用分配",
            )
        )

        result = validate_plan_intake(plan)

        self.assertEqual(result["status"], "passed")

    def test_gui_plan_textbox_blocks_are_checked_semantically(self) -> None:
        def field(label: str, value: str) -> str:
            return (
                f"- **{label}**：\n"
                "  <!-- PLAN_TEXTBOX -->\n"
                "  ---\n"
                "  ***✍️ 用户填写内容区***\n\n"
                f"  {value}\n\n"
                "  ---\n"
            )

        plan = (
            "---\n"
            "template_kind: lca_plan_input\n"
            "template_version: 1\n"
            "---\n\n"
            "# 自定义 GUI 计划\n\n"
            + field("研究主体", "PET 水瓶")
            + field(
                "功能单位（Functional Unit）",
                "在销售点交付 1,000 个 1 L PET 水瓶",
            )
            + field(
                "评估目的与预期用途",
                "比较三个情景，用于内部教学和开发测试",
            )
            + field(
                "系统边界（System Boundary）",
                "Cradle-to-Point-of-Sale；不采用自动截断；"
                "前景过程无共同产品，不实施额外分配",
            )
        )

        result = validate_plan_intake(plan)

        self.assertEqual(result["status"], "passed")

    def test_gui_plan_textbox_placeholder_still_blocks(self) -> None:
        plan = compliant_plan().replace(
            "- **功能单位 (FU)**：1 kg bottled product",
            "- **功能单位 (FU)**：\n"
            "  <!-- PLAN_TEXTBOX -->\n"
            "  ---\n"
            "  ***✍️ 用户填写内容区***\n\n"
            "  [请填写功能单位]\n\n"
            "  ---",
        )

        result = validate_plan_intake(plan)

        self.assertEqual(result["status"], "failed")
        self.assertIn(
            "PLAN-BLOCKING-FU",
            {issue["issue_id"] for issue in result["issues"]},
        )


class ReviewLoopTests(unittest.TestCase):
    def test_first_two_failures_fix_and_third_failure_stops(self) -> None:
        self.assertEqual(next_lci_review_action(1, False), "targeted_fix_and_review")
        self.assertEqual(next_lci_review_action(2, False), "targeted_fix_and_review")
        self.assertEqual(next_lci_review_action(3, False), "stop_failed")
        self.assertEqual(next_lci_review_action(2, True), "proceed_to_preflight")
        with self.assertRaises(ValueError):
            next_lci_review_action(4, False)


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas: dict[str, dict] = {}
        registry = Registry()
        for schema_root in SCHEMA_ROOTS:
            for path in sorted(schema_root.glob("*.schema.json")):
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
            "path": "workspace/inputs/plan.md",
            "source_artifact_ids": [],
            "revision_of": None,
        }

    def test_positive_manifest_stage_review_and_handoff(self) -> None:
        manifest = {
            "schema": "whole-lca/workflow-manifest",
            "version": "2.0",
            "platform": "codex",
            "orchestrator_agent": "major-orchestrator",
            "plan": self.artifact(),
            "started_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "status": "running",
            "current_stage": "plan-review",
            "import_scope": None,
            "lci_review_attempt": 0,
            "artifact_index": [self.artifact()],
            "issue_ids": [],
        }
        stage = {
            "schema": "whole-lca/stage",
            "version": "2.0",
            "stage_id": "stage-001-plan-review",
            "supersedes_stage_id": None,
            "sequence": 1,
            "stage": "plan-review",
            "agent": "eval-reviewer",
            "started_at": TIMESTAMP,
            "ended_at": TIMESTAMP,
            "status": "passed",
            "artifact_ids": ["artifact:plan"],
            "evidence_refs": ["workspace/memory/reviews/plan-review.json"],
            "issue_ids": [],
            "basis": "计划通过接收门禁。",
            "sources": [
                {
                    "type": "user-file",
                    "locator": "workspace/inputs/plan.md",
                }
            ],
            "summary": "Plan passed intake.",
        }
        review = {
            "schema": "whole-lca/review",
            "version": "2.0",
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
            "version": "2.0",
            "handoff_id": "handoff-001-plan-review",
            "supersedes_handoff_id": None,
            "stage_id": "stage-001-plan-review",
            "from_agent": "major-orchestrator",
            "to_agent": "eval-reviewer",
            "timestamp": TIMESTAMP,
            "input_artifacts": [self.artifact()],
            "decision": "Review plan intake.",
            "evidence_refs": ["workspace/inputs/plan.md"],
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
            "version": "1.1",
            "operation_id": "11111111-1111-4111-8111-111111111111",
            "status": "success",
            "endpoint": "http://localhost:8080",
            "active_database": "isolated-db",
            "target_category": "test-project",
            "lci_dir": "workspace/outputs/LCI",
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
            "version": "1.1",
            "status": "success",
            "endpoint": "http://localhost:8080",
            "product_system": entity_ref,
            "nodes": [{"id": "p1", "name": "P1"}],
            "edges": [],
            "broken_links": [],
            "disconnected_nodes": [],
            "expected_process_ids": ["p1"],
            "missing_expected_nodes": [],
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
            "version": "3.0",
            "status": "success",
            "active_database": "isolated-db",
            "impact_method": {"id": "method-id", "name": "EF"},
            "tool_versions": {"olca-ipc": "2.0"},
            "calculated_at": TIMESTAMP,
            "calculations": [
                {
                    "status": "success",
                    "product_system": entity_ref,
                    "functional_unit_amount": 1.0,
                    "allocation": None,
                    "regionalized": False,
                    "costs": False,
                    "parameters": {},
                    "calculated_at": TIMESTAMP,
                    "raw_result": {
                        "path": "workspace/outputs/reports/raw/ps1.json",
                    },
                    "resource_released": True,
                }
            ],
            "comparison_checks": [],
            "unresolved_items": [],
        }
        self.validate("import-report.schema.json", import_report)
        self.validate(
            "import-operation-status.schema.json",
            {
                "schema": "whole-lca/import-operation-status",
                "version": "1.0",
                "status": "success",
                "report": import_report,
            },
        )
        self.validate("model-graph.schema.json", graph)
        self.validate("raw-lcia-results.schema.json", raw)
        self.validate("calculation-manifest.schema.json", calculation)

        second = dict(calculation["calculations"][0])
        second["product_system"] = {"id": "ps2", "name": "Scenario 2"}
        second["raw_result"] = {
            "path": "workspace/outputs/reports/raw/ps2.json",
        }
        calculation["calculations"].append(second)
        calculation["comparison_checks"].append(
            {
                "left_product_system_id": entity_ref["id"],
                "right_product_system_id": "ps2",
                "results_equal": False,
                "status": "distinct",
                "explanation": None,
            }
        )
        self.validate("calculation-manifest.schema.json", calculation)

        legacy_calculation = {
            **calculation,
            "version": "2.0",
            "product_system": entity_ref,
            "raw_result": {
                "path": "workspace/outputs/reports/raw/ps1.json",
            },
        }
        with self.assertRaises(ValidationError):
            self.validate("calculation-manifest.schema.json", legacy_calculation)

    def test_negative_contract_examples_are_rejected(self) -> None:
        invalid_manifest = {
            "schema": "whole-lca/workflow-manifest",
            "version": "2.0",
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

        invalid_manifest["status"] = "needs_input"
        with self.assertRaises(ValidationError):
            self.validate("workflow-manifest.schema.json", invalid_manifest)

        invalid_manifest["status"] = "needs_review"
        with self.assertRaises(ValidationError):
            self.validate("workflow-manifest.schema.json", invalid_manifest)

        invalid_manifest["status"] = "awaiting_confirmation"
        with self.assertRaises(ValidationError):
            self.validate("workflow-manifest.schema.json", invalid_manifest)

    def test_terminal_status_requires_status_reason(self) -> None:
        running = {
            "schema": "whole-lca/workflow-manifest",
            "version": "2.0",
            "platform": "codex",
            "orchestrator_agent": "major-orchestrator",
            "plan": self.artifact(),
            "started_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "status": "running",
            "current_stage": "01-plan-quality-gate",
            "import_scope": None,
            "lci_review_attempt": 0,
            "artifact_index": [self.artifact()],
            "issue_ids": [],
        }
        self.validate("workflow-manifest.schema.json", running)

        failed = dict(running)
        failed["status"] = "failed"
        with self.assertRaises(ValidationError):
            self.validate("workflow-manifest.schema.json", failed)

        failed["status_reason"] = "01 计划质量门禁失败：缺少功能单位 PLAN-BLOCKING-FU。"
        failed["issue_ids"] = ["PLAN-BLOCKING-FU"]
        self.validate("workflow-manifest.schema.json", failed)

        completed = dict(running)
        completed["status"] = "completed"
        with self.assertRaises(ValidationError):
            self.validate("workflow-manifest.schema.json", completed)
        completed["status_reason"] = "第 07 阶段全部完成条件已有证据。"
        self.validate("workflow-manifest.schema.json", completed)

        failed_review = {
            "schema": "whole-lca/review",
            "version": "2.0",
            "review_id": "review-plan",
            "supersedes_review_id": None,
            "review_type": "plan",
            "attempt": 1,
            "reviewer": "eval-reviewer",
            "timestamp": TIMESTAMP,
            "status": "failed",
            "reviewed_artifacts": [self.artifact()],
            "issues": [
                {
                    "issue_id": "PLAN-BLOCKING-FU",
                    "severity": "critical",
                    "spec_ref": "01-plan-quality-gate-spec.md#2-阻断性信息",
                    "evidence_location": "workspace/inputs/plan.md",
                    "required_correction": "补充数值、基准流和物理单位。",
                    "status": "open",
                }
            ],
            "retrievable_gaps": [],
        }
        with self.assertRaises(ValidationError):
            self.validate("review.schema.json", failed_review)
        failed_review["summary"] = "计划缺少功能单位。"
        self.validate("review.schema.json", failed_review)

    def test_legacy_run_id_is_rejected(self) -> None:
        manifest = {
            "schema": "whole-lca/workflow-manifest",
            "version": "2.0",
            "run_id": "20260722T080000Z-deadbeef",
            "platform": "codex",
            "orchestrator_agent": "major-orchestrator",
            "plan": self.artifact(),
            "started_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "status": "running",
            "lci_review_attempt": 0,
            "artifact_index": [self.artifact()],
        }
        with self.assertRaises(ValidationError):
            self.validate("workflow-manifest.schema.json", manifest)

    def test_report_template_contains_traceability_and_claim_boundary(self) -> None:
        template = (
            PROJECT_ROOT
            / "harness"
            / "specs"
            / "07-lcia-calculation-reporting"
            / "references"
            / "templates"
            / "lca_report.md"
        ).read_text(encoding="utf-8")
        self.assertIn("raw_result_path", template)
        self.assertIn("原始结果位置", template)
        self.assertIn("不自动构成 ISO 认证", template)
        self.assertIn("背景数据地域代理", template)


if __name__ == "__main__":
    unittest.main()
