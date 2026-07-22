from __future__ import annotations

import re
from typing import Any


FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
FIELD_PATTERN = r"\*\*{label}\*\*\s*[:：]\s*(?P<value>[^\n]+)"
PLACEHOLDER_PATTERN = re.compile(r"^\s*\[[^\]]*(?:请|例如|填写|说明|流名称|过程名称)[^\]]*\]\s*$")
UNIT_PATTERN = re.compile(
    r"\b(?:kg|g|mg|t|tonne|L|mL|m3|m³|MJ|kWh|Wh|piece|unit|p-km|tkm)\b|千克|克|吨|升|件",
    re.IGNORECASE,
)


def _frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_PATTERN.search(text)
    if not match:
        return {}
    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def _field(text: str, *labels: str) -> str | None:
    for label in labels:
        match = re.search(FIELD_PATTERN.format(label=re.escape(label)), text)
        if match:
            return match.group("value").strip()
    return None


def _missing(value: str | None) -> bool:
    if value is None or not value.strip():
        return True
    return bool(PLACEHOLDER_PATTERN.fullmatch(value.strip()))


def _issue(issue_id: str, spec_ref: str, evidence: str, correction: str) -> dict[str, str]:
    return {
        "issue_id": issue_id,
        "severity": "critical",
        "spec_ref": spec_ref,
        "evidence_location": evidence,
        "required_correction": correction,
        "status": "open",
    }


def validate_plan_intake(text: str) -> dict[str, Any]:
    """Apply deterministic checks from the stage 01 plan quality specification."""
    issues: list[dict[str, str]] = []
    metadata = _frontmatter(text)
    if metadata.get("template_kind") != "lca_execution_plan":
        issues.append(
            _issue(
                "PLAN-FORMAT-KIND",
                "01-plan-quality-gate-spec.md#1-文件与版本",
                "YAML front matter",
                "Set template_kind to lca_execution_plan.",
            )
        )
    version = metadata.get("template_version")
    if version != "1":
        issues.append(
            _issue(
                "PLAN-FORMAT-VERSION",
                "01-plan-quality-gate-spec.md#1-文件与版本",
                "YAML front matter.template_version",
                "Migrate to supported template_version 1 or request explicit user direction.",
            )
        )

    for section in range(1, 7):
        if not re.search(rf"^##\s+{section}(?:\.|\s)", text, re.MULTILINE):
            issues.append(
                _issue(
                    f"PLAN-SECTION-{section}",
                    "01-plan-quality-gate-spec.md#1-文件与版本",
                    f"Markdown section ## {section}",
                    f"Restore the semantic top-level section numbered {section}.",
                )
            )

    required_fields = (
        ("OBJECT", ("研究对象",), "Provide a concrete study object."),
        ("PURPOSE", ("研究目的",), "Provide the intended study purpose/application."),
        ("BOUNDARY", ("生命周期阶段",), "Define the included lifecycle boundary."),
        ("CUTOFF", ("质量/能量截断比例",), "Provide a cut-off rule or an explicit no-cut-off decision."),
        ("ALLOCATION", ("多产出分配",), "State whether co-products exist and the applicable allocation rule."),
    )
    for suffix, labels, correction in required_fields:
        if _missing(_field(text, *labels)):
            issues.append(
                _issue(
                    f"PLAN-BLOCKING-{suffix}",
                    "01-plan-quality-gate-spec.md#2-阻断性信息",
                    f"field {labels[0]}",
                    correction,
                )
            )

    functional_unit = _field(text, "功能单位 (FU)", "功能单位")
    if _missing(functional_unit) or not re.search(r"\d", functional_unit or "") or not UNIT_PATTERN.search(functional_unit or ""):
        issues.append(
            _issue(
                "PLAN-BLOCKING-FU",
                "01-plan-quality-gate-spec.md#2-阻断性信息",
                "field 功能单位 (FU)",
                "Provide a numeric functional-unit amount, function/reference flow, and physical unit.",
            )
        )

    gap_ids = sorted(set(re.findall(r"\bGAP-[A-Z0-9-]+\b", text)))
    retrievable_gaps: list[str] = []
    for gap_id in gap_ids:
        gap_window_match = re.search(
            rf"{re.escape(gap_id)}(?P<body>.{{0,600}})",
            text,
            re.DOTALL,
        )
        gap_window = gap_window_match.group("body") if gap_window_match else ""
        has_type = re.search(r"gap_type\s*[:：]\s*retrievable", gap_window, re.IGNORECASE)
        has_target = re.search(r"(?:retrieval_target|检索目标)\s*[:：]\s*\S+", gap_window, re.IGNORECASE)
        has_source = re.search(r"(?:source_domain|来源域)\s*[:：]\s*\S+", gap_window, re.IGNORECASE)
        if has_type and has_target and has_source:
            retrievable_gaps.append(gap_id)
        else:
            issues.append(
                _issue(
                    f"PLAN-GAP-{gap_id.removeprefix('GAP-')}",
                    "01-plan-quality-gate-spec.md#3-可检索缺口",
                    gap_id,
                    "Add gap_type: retrievable, a retrieval target, and an allowed source domain.",
                )
            )

    return {
        "status": "passed" if not issues else "needs_input",
        "issues": issues,
        "retrievable_gaps": retrievable_gaps,
    }


def next_lci_review_action(attempt: int, passed: bool) -> str:
    """Return the only legal action after an LCI review attempt."""
    if isinstance(attempt, bool) or not isinstance(attempt, int) or not 1 <= attempt <= 3:
        raise ValueError("attempt must be an integer from 1 through 3")
    if passed:
        return "proceed_to_preflight"
    if attempt < 3:
        return "targeted_fix_and_review"
    return "stop_needs_review"
