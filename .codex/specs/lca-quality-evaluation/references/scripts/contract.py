from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SPEC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUBRIC_PATH = SPEC_ROOT / "rubric.json"
DEFAULT_SCHEMA_PATH = SPEC_ROOT / "schemas" / "lca-quality-score.schema.json"


class QualityContractError(ValueError):
    """Raised when an evaluation violates the quality contract."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualityContractError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QualityContractError(f"Expected a JSON object: {path}")
    return value


def load_rubric(path: Path = DEFAULT_RUBRIC_PATH) -> dict[str, Any]:
    rubric = _read_json(path)
    validate_rubric(rubric)
    return rubric


def validate_rubric(rubric: dict[str, Any]) -> None:
    if rubric.get("schema") != "lca-quality/rubric":
        raise QualityContractError("Unexpected rubric schema")
    if rubric.get("version") != "2.1":
        raise QualityContractError("Unsupported rubric version")

    dimensions = rubric.get("dimensions")
    criteria = rubric.get("criteria")
    coverage = rubric.get("artifact_coverage")
    applicability_rules = rubric.get("applicability_rules")
    if not isinstance(dimensions, list) or not dimensions:
        raise QualityContractError("Rubric dimensions must be a non-empty list")
    if not isinstance(criteria, list) or not criteria:
        raise QualityContractError("Rubric criteria must be a non-empty list")
    if not isinstance(coverage, list) or not coverage:
        raise QualityContractError("Artifact coverage must be a non-empty list")
    if not isinstance(applicability_rules, list) or not applicability_rules:
        raise QualityContractError("Applicability rules must be a non-empty list")

    dimension_ids = [item.get("dimension_id") for item in dimensions]
    criterion_ids = [item.get("criterion_id") for item in criteria]
    artifact_kinds = [item.get("kind") for item in coverage]
    for label, values in (
        ("dimension", dimension_ids),
        ("criterion", criterion_ids),
        ("artifact kind", artifact_kinds),
    ):
        if any(not isinstance(value, str) or not value for value in values):
            raise QualityContractError(f"Every {label} ID must be a non-empty string")
        if len(values) != len(set(values)):
            raise QualityContractError(f"Duplicate {label} ID")

    dimension_set = set(dimension_ids)
    criterion_set = set(criterion_ids)
    valid_rules = {
        "always",
        "lca-only",
        "third-party-only",
        "critical-review-if-conducted",
        "public-comparison-only",
    }
    routed_criteria: list[str] = []
    for item in applicability_rules:
        if item.get("rule") not in valid_rules:
            raise QualityContractError(f"Unknown applicability rule: {item.get('rule')}")
        refs = item.get("criterion_ids")
        if not isinstance(refs, list) or not refs:
            raise QualityContractError(f"Applicability rule {item.get('rule')} has no criteria")
        routed_criteria.extend(refs)
    if len(routed_criteria) != len(set(routed_criteria)):
        raise QualityContractError("A criterion has more than one applicability rule")
    if set(routed_criteria) != criterion_set:
        raise QualityContractError("Applicability rules do not cover the complete criterion set")

    referenced_criteria: set[str] = set()
    for item in criteria:
        if item.get("dimension_id") not in dimension_set:
            raise QualityContractError(
                f"Criterion {item.get('criterion_id')} references an unknown dimension"
            )
        if not item.get("title") or not item.get("required_evidence"):
            raise QualityContractError(
                f"Criterion {item.get('criterion_id')} lacks title or required evidence"
            )
        refs = item.get("standard_refs")
        if not isinstance(refs, list) or not refs:
            raise QualityContractError(
                f"Criterion {item.get('criterion_id')} lacks standard references"
            )

    for item in coverage:
        refs = item.get("criterion_ids")
        if not isinstance(refs, list) or not refs:
            raise QualityContractError(f"Artifact kind {item.get('kind')} has no criteria")
        unknown = set(refs) - criterion_set
        if unknown:
            raise QualityContractError(
                f"Artifact kind {item.get('kind')} references unknown criteria: {sorted(unknown)}"
            )
        referenced_criteria.update(refs)
        patterns = item.get("path_patterns")
        if not isinstance(patterns, list) or not patterns:
            raise QualityContractError(f"Artifact kind {item.get('kind')} has no path patterns")

    uncovered = criterion_set - referenced_criteria
    if uncovered:
        raise QualityContractError(
            f"Criteria lack artifact coverage: {sorted(uncovered)}"
        )


def _schema_errors(data: dict[str, Any], schema_path: Path) -> list[str]:
    schema = _read_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    ]


def validate_evaluation(
    data: dict[str, Any],
    rubric: dict[str, Any] | None = None,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> None:
    rubric = rubric or load_rubric()
    errors = _schema_errors(data, schema_path)
    if errors:
        raise QualityContractError("Schema validation failed:\n" + "\n".join(errors))
    if data["rubric_version"] != rubric["version"]:
        raise QualityContractError("Evaluation rubric version does not match loaded rubric")

    expected_standards = {
        (item["id"], item["edition"]): item for item in rubric["standards"]
    }
    actual_standards = {
        (item["id"], item["edition"]): item for item in data["standards"]
    }
    if len(actual_standards) != len(data["standards"]):
        raise QualityContractError("Duplicate standard ID and edition")
    for key, expected in expected_standards.items():
        actual = actual_standards.get(key)
        if actual is None or actual["path"] != expected["path"]:
            raise QualityContractError(f"Missing or changed controlled standard: {key}")

    input_ids = [item["artifact_id"] for item in data["inputs"]]
    if len(input_ids) != len(set(input_ids)):
        raise QualityContractError("Duplicate input artifact ID")

    expected_criteria = {item["criterion_id"]: item for item in rubric["criteria"]}
    actual_criteria = {item["criterion_id"]: item for item in data["criteria"]}
    if len(actual_criteria) != len(data["criteria"]):
        raise QualityContractError("Duplicate criterion ID in evaluation")
    if set(actual_criteria) != set(expected_criteria):
        missing = sorted(set(expected_criteria) - set(actual_criteria))
        extra = sorted(set(actual_criteria) - set(expected_criteria))
        raise QualityContractError(f"Criterion set mismatch; missing={missing}, extra={extra}")

    rule_by_criterion = {
        criterion_id: item["rule"]
        for item in rubric["applicability_rules"]
        for criterion_id in item["criterion_ids"]
    }
    application = data["applicability"]
    expected_applicability: dict[str, str] = {}
    for criterion_id, rule in rule_by_criterion.items():
        if rule == "always":
            value = "applicable"
        elif rule == "lca-only":
            value = {
                "lca": "applicable",
                "lci": "not_applicable",
                "unresolved": "unresolved",
            }[application["study_type"]]
        elif rule == "third-party-only":
            value = {
                "yes": "applicable",
                "no": "not_applicable",
                "unresolved": "unresolved",
            }[application["third_party_communication"]]
        elif rule == "critical-review-if-conducted":
            value = {
                "none": "not_applicable",
                "expert": "applicable",
                "panel": "applicable",
                "unresolved": "unresolved",
            }[application["critical_review_type"]]
        else:
            value = {
                "yes": "applicable",
                "no": "not_applicable",
                "unresolved": "unresolved",
            }[application["public_comparative_assertion"]]
        expected_applicability[criterion_id] = value

    for criterion_id, expected in expected_criteria.items():
        actual = actual_criteria[criterion_id]
        for field in ("dimension_id", "title", "standard_refs"):
            if actual[field] != expected[field]:
                raise QualityContractError(
                    f"{criterion_id} field {field} does not match rubric"
                )
        applicability = actual["applicability"]
        if applicability != expected_applicability[criterion_id]:
            raise QualityContractError(
                f"{criterion_id} applicability does not match the fixed rule "
                f"{rule_by_criterion[criterion_id]}"
            )
        gate = actual["gate_status"]
        level = actual["evidence_level"]
        if applicability == "not_applicable":
            if gate != "not_applicable" or level is not None:
                raise QualityContractError(
                    f"{criterion_id} not_applicable requires gate not_applicable and null level"
                )
        else:
            if gate == "not_applicable" or level is None:
                raise QualityContractError(
                    f"{criterion_id} applicable/unresolved requires a gate and 0-3 level"
                )
        if applicability == "unresolved" and gate != "needs_human_review":
            raise QualityContractError(
                f"{criterion_id} unresolved applicability requires needs_human_review"
            )
        if gate in {"fail", "needs_human_review"} and actual["issue_id"] is None:
            raise QualityContractError(f"{criterion_id} requires an issue ID")
        if gate == "pass" and actual["issue_id"] is not None:
            raise QualityContractError(f"{criterion_id} pass cannot carry an issue ID")

    expected_coverage = {item["kind"]: item for item in rubric["artifact_coverage"]}
    actual_coverage = {item["kind"]: item for item in data["artifact_coverage"]}
    if len(actual_coverage) != len(data["artifact_coverage"]):
        raise QualityContractError("Duplicate artifact coverage kind")
    if set(actual_coverage) != set(expected_coverage):
        raise QualityContractError("Artifact coverage kinds do not match rubric")
    for kind, expected in expected_coverage.items():
        actual = actual_coverage[kind]
        if actual["required"] != expected["required"]:
            raise QualityContractError(f"Artifact coverage required flag changed for {kind}")
        if set(actual["criterion_ids"]) != set(expected["criterion_ids"]):
            raise QualityContractError(f"Artifact coverage criteria changed for {kind}")
        if expected["required"] and actual["status"] == "not_applicable":
            raise QualityContractError(f"Required artifact kind cannot be not_applicable: {kind}")

        active_criterion_ids = [
            criterion_id
            for criterion_id in expected["criterion_ids"]
            if actual_criteria[criterion_id]["applicability"] != "not_applicable"
        ]
        coverage_required = expected["required"] or bool(active_criterion_ids)
        matched_inputs = {
            item["artifact_id"]: item
            for item in data["inputs"]
            if item["artifact_id"] in actual["matched_artifact_ids"]
        }
        invalid_match = len(matched_inputs) != len(actual["matched_artifact_ids"]) or any(
            item["kind"] != kind
            or item["file_status"] != "present"
            or item["schema_status"] == "invalid"
            for item in matched_inputs.values()
        )
        if actual["status"] == "covered" and (
            not actual["matched_artifact_ids"] or invalid_match
        ):
            raise QualityContractError(f"Covered artifact kind lacks valid matched inputs: {kind}")
        if coverage_required and actual["status"] != "covered":
            insufficient = [
                criterion_id
                for criterion_id in active_criterion_ids
                if actual_criteria[criterion_id]["gate_status"] != "fail"
                or actual_criteria[criterion_id]["evidence_level"] != 0
            ]
            if insufficient:
                raise QualityContractError(
                    f"Missing artifact kind {kind} must fail linked criteria at level 0: "
                    f"{sorted(insufficient)}"
                )

    expected_dimensions = {item["dimension_id"]: item for item in rubric["dimensions"]}
    actual_dimensions = {item["dimension_id"]: item for item in data["dimensions"]}
    if len(actual_dimensions) != len(data["dimensions"]):
        raise QualityContractError("Duplicate dimension ID")
    if set(actual_dimensions) != set(expected_dimensions):
        raise QualityContractError("Dimension set does not match rubric")
    for dimension_id, expected in expected_dimensions.items():
        actual = actual_dimensions[dimension_id]
        if actual["name"] != expected["name"]:
            raise QualityContractError(f"Dimension name changed: {dimension_id}")
        applicable = [
            item
            for item in data["criteria"]
            if item["dimension_id"] == dimension_id
            and item["applicability"] != "not_applicable"
        ]
        criterion_ids = [item["criterion_id"] for item in applicable]
        distribution = Counter(str(item["evidence_level"]) for item in applicable)
        expected_distribution = {str(level): distribution[str(level)] for level in range(4)}
        expected_level = min((item["evidence_level"] for item in applicable), default=None)
        if set(actual["criterion_ids"]) != set(criterion_ids):
            raise QualityContractError(f"Dimension criterion list mismatch: {dimension_id}")
        if actual["applicable_count"] != len(applicable):
            raise QualityContractError(f"Dimension applicable count mismatch: {dimension_id}")
        if actual["distribution"] != expected_distribution:
            raise QualityContractError(f"Dimension distribution mismatch: {dimension_id}")
        if actual["evidence_level"] != expected_level:
            raise QualityContractError(f"Dimension shortfall level mismatch: {dimension_id}")

    issue_ids = [item["issue_id"] for item in data["issues"]]
    if len(issue_ids) != len(set(issue_ids)):
        raise QualityContractError("Duplicate issue ID")
    issues_by_id = {item["issue_id"]: item for item in data["issues"]}
    referenced_issue_ids: set[str] = set()
    for criterion in data["criteria"]:
        issue_id = criterion["issue_id"]
        if issue_id is not None:
            referenced_issue_ids.add(issue_id)
            issue = issues_by_id.get(issue_id)
            if issue is None or issue["criterion_id"] != criterion["criterion_id"]:
                raise QualityContractError(
                    f"Criterion {criterion['criterion_id']} has an invalid issue reference"
                )
    orphan_issues = set(issues_by_id) - referenced_issue_ids
    if orphan_issues:
        raise QualityContractError(f"Issues are not referenced by criteria: {sorted(orphan_issues)}")

    failed = sorted(
        item["criterion_id"] for item in data["criteria"] if item["gate_status"] == "fail"
    )
    human = sorted(
        item["criterion_id"]
        for item in data["criteria"]
        if item["gate_status"] == "needs_human_review"
    )
    overall = data["overall"]
    if sorted(overall["failed_criteria"]) != failed:
        raise QualityContractError("overall.failed_criteria is inconsistent")
    if sorted(overall["human_review_criteria"]) != human:
        raise QualityContractError("overall.human_review_criteria is inconsistent")
    supported = data["workflow_contract_version"] in rubric[
        "supported_workflow_contract_versions"
    ]
    if failed and overall["status"] != "fail":
        raise QualityContractError("Any failed criterion requires overall fail")
    if not failed and (human or not supported) and overall["status"] != "needs_human_review":
        raise QualityContractError(
            "Human-review criteria or unknown workflow version require needs_human_review"
        )
    if not failed and not human and supported and overall["status"] not in {
        "pass",
        "conditional_pass",
    }:
        raise QualityContractError("Overall status is inconsistent with criterion gates")
    applicable_levels = [
        item["evidence_level"]
        for item in data["criteria"]
        if item["applicability"] != "not_applicable"
    ]
    if overall["status"] == "pass" and any(level != 3 for level in applicable_levels):
        raise QualityContractError("Overall pass requires evidence level 3 for every applicable criterion")


def load_and_validate(
    input_path: Path,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rubric = load_rubric(rubric_path)
    data = _read_json(input_path)
    validate_evaluation(data, rubric, schema_path)
    return data, rubric


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, list):
        value = "; ".join(str(item) for item in value) or "—"
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _table(headers: list[str], rows: list[list[Any]], aligns: list[str] | None = None) -> str:
    aligns = aligns or [":---"] * len(headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(aligns) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def render_markdown(data: dict[str, Any], rubric: dict[str, Any] | None = None) -> str:
    rubric = rubric or load_rubric()
    validate_evaluation(data, rubric)
    overall = data["overall"]
    applicability = data["applicability"]
    lines = [
        "---",
        "template_kind: lca_quality_report",
        'template_version: "2.1"',
        f'review_id: "{data["review_id"]}"',
        f'rubric_version: "{data["rubric_version"]}"',
        "---",
        "",
        "# LCA 质量评估报告",
        "",
        "> 本报告是项目质量治理评价，不构成 ISO 认证、正式符合性认证或独立关键审查。",
        "",
        "## 1. 评估摘要",
        "",
        _table(
            ["项目", "内容"],
            [
                ["总体状态", overall["status"]],
                ["允许用途", overall["permitted_use"]],
                ["评价时间", data["evaluated_at"]],
                ["评估器", f'{data["evaluator"]["platform"]}/{data["evaluator"]["agent"]}'],
                ["结论理由", overall["rationale"]],
            ],
        ),
        "",
        "## 2. 适用性声明",
        "",
        _table(
            ["项目", "结论", "证据/理由"],
            [
                ["研究类型", applicability["study_type"], applicability["evidence_refs"]],
                ["预期用途", applicability["intended_application"], applicability["evidence_refs"]],
                ["预期受众", applicability["intended_audience"], applicability["evidence_refs"]],
                ["第三方沟通", applicability["third_party_communication"], applicability["evidence_refs"]],
                ["公开比较声明", applicability["public_comparative_assertion"], applicability["evidence_refs"]],
                ["LCIA 可选元素", applicability["optional_lcia_elements"], applicability["evidence_refs"]],
                ["关键审查", applicability["critical_review_type"], applicability["evidence_refs"]],
            ],
        ),
        "",
        "## 3. 标准依据",
        "",
        _table(
            ["标准", "版本", "原文路径", "SHA-256", "定位"],
            [[item["id"], item["edition"], item["path"], item["sha256"], item["locators"]] for item in data["standards"]],
        ),
        "",
        "## 4. 输入证据与产物覆盖",
        "",
        _table(
            ["Artifact ID", "类型", "路径", "文件状态", "Schema 状态", "SHA-256", "说明"],
            [[item["artifact_id"], item["kind"], item["path"], item["file_status"], item["schema_status"], item["sha256"], item["details"]] for item in data["inputs"]],
        ),
        "",
        "### 固定产物覆盖",
        "",
        _table(
            ["类型", "必需", "状态", "匹配 Artifact", "关联检查项"],
            [[item["kind"], item["required"], item["status"], item["matched_artifact_ids"], item["criterion_ids"]] for item in data["artifact_coverage"]],
        ),
        "",
        "## 5. 维度汇总",
        "",
        _table(
            ["维度", "短板等级", "0", "1", "2", "3", "适用项数"],
            [[item["name"], item["evidence_level"], item["distribution"]["0"], item["distribution"]["1"], item["distribution"]["2"], item["distribution"]["3"], item["applicable_count"]] for item in data["dimensions"]],
            [":---", "---:", "---:", "---:", "---:", "---:", "---:"],
        ),
        "",
        "## 6. 逐项评分",
        "",
        _table(
            ["ID", "检查项", "适用性", "门禁", "等级", "标准引用", "证据", "发现/缺口", "Issue", "责任建议", "复审条件"],
            [[item["criterion_id"], item["title"], item["applicability"], item["gate_status"], item["evidence_level"], item["standard_refs"], item["evidence_refs"], item["finding"], item["issue_id"], item["owner"], item["recheck_condition"]] for item in data["criteria"]],
            [":---", ":---", ":---", ":---", "---:", ":---", ":---", ":---", ":---", ":---", ":---"],
        ),
        "",
        "## 7. 问题与修正要求",
        "",
        _table(
            ["Issue ID", "严重度", "检查项", "状态", "发现", "修正要求", "证据"],
            [[item["issue_id"], item["severity"], item["criterion_id"], item["status"], item["finding"], item["required_action"], item["evidence_refs"]] for item in data["issues"]],
        ),
        "",
        "## 8. 限制与建议",
        "",
        "### 允许使用边界",
        "",
        f'- {overall["permitted_use"]}',
        "",
        "### 研究限制",
        "",
        *([f"- {item}" for item in overall["limitations"]] or ["- 无记录限制。"]),
        "",
        "### 评估器限制",
        "",
        *([f"- {item}" for item in data["evaluator_limitations"]] or ["- 无记录限制。"]),
        "",
        "### 建议",
        "",
        *([f"- {item}" for item in data["recommendations"]] or ["- 无。"]),
        "",
    ]
    return "\n".join(lines)
