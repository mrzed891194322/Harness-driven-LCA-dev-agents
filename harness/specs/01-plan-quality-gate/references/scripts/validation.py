from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
DEFAULT_REFERENCE_ROOTS = (
    PROJECT_ROOT / "harness" / "knowledge" / "inputs" / "user_ref" / "file",
    PROJECT_ROOT / "harness" / "knowledge" / "inputs" / "user_ref" / "data",
)
REFERENCE_CONTROL_FILES = {".gitignore", "readme.md"}
FIELD_PATTERN = r"\*\*{label}\*\*\s*[:：]"
PLAN_INPUT_START_PATTERN = re.compile(r"^\s*<!--\s*PLAN_INPUT\b[^\n]*-->", re.DOTALL)
PLAN_INPUT_VALUE_END_PATTERN = re.compile(
    r"\*{2,3}\s*✍\ufe0f?\s*用户填写(?:内容)?区\s*\*{2,3}"
)
LEGACY_INPUT_PATTERN = re.compile(
    r"^\s*(?:<!--\s*PLAN_TEXTBOX\s*-->\s*)?"
    r"---[ \t]*\n"
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
                r"无(?:副产品|多产出|共同产品)|"
                r"不(?:实施|进行|需要)(?:额外)?分配|不适用(?:分配)?|"
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


def build_reference_inventory(
    reference_roots: Iterable[Path] | None = None,
) -> dict[str, list[str]]:
    """Enumerate runtime references without applying Git ignore rules."""
    roots = tuple(reference_roots) if reference_roots is not None else DEFAULT_REFERENCE_ROOTS
    displayed_roots: list[str] = []
    files: set[str] = set()

    for raw_root in roots:
        root = Path(raw_root).resolve()
        try:
            displayed_roots.append(root.relative_to(PROJECT_ROOT).as_posix())
        except ValueError:
            displayed_roots.append(root.as_posix())
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.name.casefold() in REFERENCE_CONTROL_FILES:
                continue
            resolved = path.resolve()
            try:
                files.add(resolved.relative_to(PROJECT_ROOT).as_posix())
            except ValueError:
                files.add(resolved.as_posix())

    return {
        "roots": sorted(set(displayed_roots)),
        "files": sorted(files),
    }


def validate_plan_intake(
    text: str,
    *,
    reference_roots: Iterable[Path] | None = None,
) -> dict[str, Any]:
    """Apply deterministic checks from the stage 01 plan quality specification."""
    issues: list[dict[str, str]] = []

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

    # Optional hints only. User plans do not need GAP-* tokens or structured
    # gap fields; reviewers mint tracking IDs into review.retrievable_gaps.
    retrievable_gaps = sorted(set(re.findall(r"\bGAP-[A-Z0-9-]+\b", text)))

    return {
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "retrievable_gaps": retrievable_gaps,
        "reference_inventory": build_reference_inventory(reference_roots),
    }
