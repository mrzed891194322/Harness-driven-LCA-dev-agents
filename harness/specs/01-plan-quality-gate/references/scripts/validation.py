from __future__ import annotations

import re
from typing import Any


FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
FIELD_PATTERN = r"\*\*{label}\*\*\s*[:：]"
PLAN_INPUT_START_PATTERN = re.compile(r"^\s*<!--\s*PLAN_INPUT\b[^\n]*-->", re.DOTALL)
PLAN_INPUT_VALUE_END_PATTERN = re.compile(
    r"\*{2,3}\s*✍\ufe0f?\s*用户填写(?:内容)?区\s*\*{2,3}"
)
LEGACY_INPUT_PATTERN = re.compile(
    r"^\s*---[ \t]*\n"
    r"[ \t]*\*{2,3}\s*✍\ufe0f?\s*用户填写内容区\s*\*{2,3}[ \t]*\n"
    r"(?P<value>.*?)"
    r"^[ \t]*---[ \t]*(?=\n|$)",
    re.DOTALL | re.MULTILINE,
)
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
        if not match:
            continue
        tail = text[match.end():]
        first_line, _, _ = tail.partition("\n")
        inline = re.sub(r"<!--.*?-->", "", first_line).strip()
        if inline:
            return inline

        explicit = PLAN_INPUT_START_PATTERN.match(tail)
        if explicit:
            marker = PLAN_INPUT_VALUE_END_PATTERN.search(tail, explicit.end())
            if marker:
                return tail[explicit.end():marker.start()].strip()

        legacy = LEGACY_INPUT_PATTERN.match(tail)
        if legacy:
            return legacy.group("value").strip()
    return None


def _missing(value: str | None) -> bool:
    if value is None or not value.strip():
        return True
    return bool(PLACEHOLDER_PATTERN.fullmatch(value.strip()))


def _has_embedded_decision(text: str, suffix: str) -> bool:
    """Recognize decisions written inside a broader GUI free-text field."""
    if suffix == "CUTOFF":
        return bool(
            re.search(
                r"(?:不采用|不设置|无|零|0\s*%|\d+(?:\.\d+)?\s*%)"
                r"[^\n]{0,40}(?:截断|cut[\s-]*off)"
                r"|(?:截断|cut[\s-]*off)[^\n]{0,40}"
                r"(?:不采用|不设置|无|零|0\s*%|\d+(?:\.\d+)?\s*%)",
                text,
                re.IGNORECASE,
            )
        )
    if suffix == "ALLOCATION":
        return bool(
            re.search(
                r"无(?:副产品|多产出)|不适用(?:分配)?|"
                r"(?:分配|allocation)[^\n]{0,50}"
                r"(?:质量|能量|经济|物理|系统扩展|替代)",
                text,
                re.IGNORECASE,
            )
        )
    return False


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
    if metadata.get("template_kind") != "lca_plan_input":
        issues.append(
            _issue(
                "PLAN-FORMAT-KIND",
                "01-plan-quality-gate-spec.md#1-文件与版本",
                "YAML front matter",
                "Set template_kind to lca_plan_input.",
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

    legacy_reference_paths = sorted(
        set(
            re.findall(
                r"harness/knowledge/inputs/(?:user_file|user_data)(?:/[^\s`'\"<>)]*)?",
                text,
            )
        )
    )
    for path in legacy_reference_paths:
        kind = "file" if "/user_file" in path else "data"
        issues.append(
            _issue(
                "PLAN-REF-LEGACY-PATH",
                "01-plan-quality-gate-spec.md#1-文件与版本",
                path,
                "Replace the legacy path with "
                f"harness/knowledge/inputs/user_ref/{kind}/...",
            )
        )

    required_fields = (
        ("OBJECT", ("研究对象", "研究主体"), "Provide a concrete study object."),
        (
            "PURPOSE",
            ("研究目的", "评估目的与预期用途"),
            "Provide the intended study purpose/application.",
        ),
        (
            "BOUNDARY",
            ("生命周期阶段", "系统边界（System Boundary）", "系统边界"),
            "Define the included lifecycle boundary.",
        ),
        ("CUTOFF", ("质量/能量截断比例",), "Provide a cut-off rule or an explicit no-cut-off decision."),
        ("ALLOCATION", ("多产出分配",), "State whether co-products exist and the applicable allocation rule."),
    )
    for suffix, labels, correction in required_fields:
        value = _field(text, *labels)
        if _missing(value) and not _has_embedded_decision(text, suffix):
            issues.append(
                _issue(
                    f"PLAN-BLOCKING-{suffix}",
                    "01-plan-quality-gate-spec.md#2-阻断性信息",
                    f"field {labels[0]}",
                    correction,
                )
            )

    functional_unit = _field(
        text,
        "功能单位 (FU)",
        "功能单位（Functional Unit）",
        "功能单位",
    )
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
