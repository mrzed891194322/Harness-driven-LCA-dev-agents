from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from contract import (
    QualityContractError,
    load_rubric,
    render_markdown,
    validate_evaluation,
)


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
HASH = "a" * 64
REVIEW_ID = "20260722T090000Z-cafebabe"
TIMESTAMP = "2026-07-22T09:00:00Z"


def build_evaluation() -> dict:
    rubric = load_rubric()
    criteria = []
    for item in rubric["criteria"]:
        not_applicable = item["criterion_id"].startswith("PUB-") or item[
            "criterion_id"
        ] in {"REP-05", "REP-08"}
        criteria.append(
            {
                "criterion_id": item["criterion_id"],
                "dimension_id": item["dimension_id"],
                "title": item["title"],
                "applicability": "not_applicable" if not_applicable else "applicable",
                "gate_status": "not_applicable" if not_applicable else "pass",
                "evidence_level": None if not_applicable else 3,
                "standard_refs": item["standard_refs"],
                "evidence_refs": ["artifact:plan#scope"],
                "finding": "内部用途证据支持不适用。" if not_applicable else "证据完整并已验证。",
                "issue_id": None,
                "owner": "LCA practitioner",
                "recheck_condition": "用途或证据变化时复评。",
            }
        )

    dimensions = []
    for dimension in rubric["dimensions"]:
        applicable = [
            item
            for item in criteria
            if item["dimension_id"] == dimension["dimension_id"]
            and item["applicability"] != "not_applicable"
        ]
        distribution = Counter(str(item["evidence_level"]) for item in applicable)
        dimensions.append(
            {
                "dimension_id": dimension["dimension_id"],
                "name": dimension["name"],
                "evidence_level": min(
                    (item["evidence_level"] for item in applicable), default=None
                ),
                "distribution": {
                    str(level): distribution[str(level)] for level in range(4)
                },
                "applicable_count": len(applicable),
                "criterion_ids": [item["criterion_id"] for item in applicable],
            }
        )

    inputs = []
    coverage = []
    for index, item in enumerate(rubric["artifact_coverage"], start=1):
        artifact_id = f"artifact:quality-input-{index:02d}"
        optional = not item["required"]
        if not optional:
            inputs.append(
                {
                    "artifact_id": artifact_id,
                    "kind": item["kind"],
                    "path": item["path_patterns"][0],
                    "file_status": "present",
                    "schema_status": "valid",
                    "sha256": HASH,
                    "details": "Fixture evidence.",
                }
            )
        coverage.append(
            {
                "kind": item["kind"],
                "required": item["required"],
                "status": "not_applicable" if optional else "covered",
                "criterion_ids": item["criterion_ids"],
                "matched_artifact_ids": [] if optional else [artifact_id],
            }
        )

    return {
        "schema": "lca-quality/score",
        "version": "2.1",
        "rubric_version": rubric["version"],
        "workflow_contract_version": "2.0",
        "review_id": REVIEW_ID,
        "evaluated_at": TIMESTAMP,
        "evaluator": {"agent": "lca-quality-evaluator", "platform": "codex"},
        "standards": [
            {"id": "ISO 14040", "edition": "2006", "path": rubric["standards"][0]["path"], "sha256": HASH, "locators": ["5.1", "6"]},
            {"id": "ISO 14044", "edition": "2006", "path": rubric["standards"][1]["path"], "sha256": HASH, "locators": ["4.1-4.5", "5.1-5.3", "6.1-6.3"]},
        ],
        "applicability": {
            "study_type": "lca",
            "intended_application": "内部改进与开发回归",
            "intended_audience": "项目团队",
            "third_party_communication": "no",
            "public_comparative_assertion": "no",
            "optional_lcia_elements": ["none"],
            "critical_review_type": "none",
            "evidence_refs": ["artifact:plan#scope"],
        },
        "inputs": inputs,
        "artifact_coverage": coverage,
        "criteria": criteria,
        "dimensions": dimensions,
        "issues": [],
        "overall": {"status": "pass", "rationale": "全部适用门禁通过。", "failed_criteria": [], "human_review_criteria": [], "limitations": ["仅适用于声明的内部用途。"], "permitted_use": "内部质量治理与开发回归。"},
        "evaluator_limitations": ["自动评价不能替代独立关键审查。"],
        "recommendations": ["用途变化时重新评价适用性。"],
    }


def recompute_dimensions(data: dict) -> None:
    for dimension in data["dimensions"]:
        applicable = [item for item in data["criteria"] if item["dimension_id"] == dimension["dimension_id"] and item["applicability"] != "not_applicable"]
        distribution = Counter(str(item["evidence_level"]) for item in applicable)
        dimension["evidence_level"] = min((item["evidence_level"] for item in applicable), default=None)
        dimension["distribution"] = {str(level): distribution[str(level)] for level in range(4)}
        dimension["applicable_count"] = len(applicable)
        dimension["criterion_ids"] = [item["criterion_id"] for item in applicable]


class RubricTests(unittest.TestCase):
    def test_fixed_rubric_is_complete_and_unique(self) -> None:
        rubric = load_rubric()
        ids = [item["criterion_id"] for item in rubric["criteria"]]
        self.assertEqual(len(ids), 52)
        self.assertEqual(len(ids), len(set(ids)))
        required_kinds = {item["kind"] for item in rubric["artifact_coverage"] if item["required"]}
        self.assertTrue({"execution-plan", "workflow-manifest", "workflow-history", "lci-flows", "lci-processes", "lci-product-systems", "lci-mapping-report", "import-report", "model-graph", "raw-lcia-results", "calculation-manifest", "lca-report"}.issubset(required_kinds))

    def test_current_delivery_files_are_covered(self) -> None:
        rubric_text = json.dumps(load_rubric(), ensure_ascii=False)
        for value in ("workspace/memory/manifest.json", "workspace/memory/stages/*.json", "workspace/results/import_report.json", "workspace/results/model_graph/*.json", "workspace/results/raw/*.json", "workspace/results/calculation_manifest.json", "workspace/results/lca_report.md", "LCI/flows/*.json", "LCI/processes/*.json", "LCI/product_systems/*.json", "LCI/human_readable_mapping.md"):
            self.assertIn(value, rubric_text)
        self.assertNotIn("<run_id>", rubric_text)

        model_graph = next(
            item
            for item in load_rubric()["artifact_coverage"]
            if item["kind"] == "model-graph"
        )
        self.assertTrue({"LCI-03", "LCI-05"}.issubset(model_graph["criterion_ids"]))
        lci_model = next(
            item
            for item in load_rubric()["criteria"]
            if item["criterion_id"] == "LCI-05"
        )
        self.assertIn("节点非空", lci_model["required_evidence"])


class EvaluationContractTests(unittest.TestCase):
    def test_valid_internal_evaluation_and_markdown(self) -> None:
        data = build_evaluation()
        validate_evaluation(data)
        report = render_markdown(data)
        self.assertIn('template_version: "2.1"', report)
        self.assertIn("总体状态 | pass", report)
        self.assertIn("不构成 ISO 认证", report)
        self.assertNotIn("run_id:", report)
        for item in data["criteria"]:
            self.assertIn(item["criterion_id"], report)

    def test_legacy_run_id_is_rejected(self) -> None:
        data = build_evaluation()
        data["run_id"] = "20260722T080000Z-deadbeef"
        with self.assertRaises(QualityContractError):
            validate_evaluation(data)

    def test_missing_evidence_produces_fail_and_zero(self) -> None:
        data = build_evaluation()
        criterion = next(item for item in data["criteria"] if item["criterion_id"] == "LCI-03")
        criterion.update(gate_status="fail", evidence_level=0, finding="缺少数据有效性检查。", issue_id="LCAQ-LCI-03-0001")
        data["issues"] = [{"issue_id": "LCAQ-LCI-03-0001", "criterion_id": "LCI-03", "severity": "critical", "status": "open", "finding": "缺少数据有效性检查。", "required_action": "补充质量或能量平衡及异常处置证据。", "evidence_refs": ["artifact:quality-input-05"]}]
        data["overall"].update(status="fail", rationale="存在适用硬门禁失败。", failed_criteria=["LCI-03"])
        recompute_dimensions(data)
        validate_evaluation(data)
        dimension = next(item for item in data["dimensions"] if item["dimension_id"] == "data-quality-sources")
        self.assertEqual(dimension["evidence_level"], 0)

    def test_average_cannot_replace_shortfall_level(self) -> None:
        data = build_evaluation()
        data["dimensions"][0]["evidence_level"] = 2
        with self.assertRaisesRegex(QualityContractError, "shortfall"):
            validate_evaluation(data)

    def test_unknown_workflow_version_requires_human_review(self) -> None:
        data = build_evaluation()
        data["workflow_contract_version"] = "99.0"
        data["overall"].update(status="needs_human_review", rationale="工作流契约版本未受支持。")
        validate_evaluation(data)
        data["overall"]["status"] = "pass"
        with self.assertRaisesRegex(QualityContractError, "unknown workflow"):
            validate_evaluation(data)

    def test_missing_required_artifact_must_propagate_to_linked_criteria(self) -> None:
        data = build_evaluation()
        coverage = next(
            item for item in data["artifact_coverage"] if item["kind"] == "model-graph"
        )
        coverage["status"] = "missing"
        coverage["matched_artifact_ids"] = []
        with self.assertRaisesRegex(QualityContractError, "must fail linked criteria"):
            validate_evaluation(data)

    def test_pass_requires_every_applicable_item_at_level_three(self) -> None:
        data = build_evaluation()
        criterion = next(
            item for item in data["criteria"] if item["criterion_id"] == "INT-05"
        )
        criterion["evidence_level"] = 2
        recompute_dimensions(data)
        with self.assertRaisesRegex(QualityContractError, "Overall pass"):
            validate_evaluation(data)

    def test_core_criterion_cannot_be_hidden_as_not_applicable(self) -> None:
        data = build_evaluation()
        criterion = next(
            item for item in data["criteria"] if item["criterion_id"] == "LCI-01"
        )
        criterion.update(
            applicability="not_applicable",
            gate_status="not_applicable",
            evidence_level=None,
        )
        recompute_dimensions(data)
        with self.assertRaisesRegex(QualityContractError, "fixed rule"):
            validate_evaluation(data)

    def test_renderer_refuses_to_overwrite(self) -> None:
        data = build_evaluation()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            score = root / "score.json"
            output = root / "report.md"
            score.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            output.write_text("existing", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_ROOT / "cli.py"),
                    "--input",
                    str(score),
                    "--output",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_skill_script_runs_from_documented_path(self) -> None:
        data = build_evaluation()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            score = root / "score.json"
            output = root / "report.md"
            score.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(
                        PROJECT_ROOT
                        / ".codex"
                        / "skills"
                        / "evaluate-lca-quality"
                        / "scripts"
                        / "render_quality_report.py"
                    ),
                    "--input",
                    str(score),
                    "--output",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("# LCA 质量评估报告", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
