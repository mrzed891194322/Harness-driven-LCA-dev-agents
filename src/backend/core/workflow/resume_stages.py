"""Stage codes for resume-lca (shared by orchestrator and services)."""

from __future__ import annotations

import re

RESUME_CODES: dict[str, str] = {
    "02": "02-inventory-extraction",
    "03": "03-dataset-mapping",
    "04": "04-openlca-reporting",
}


def normalize_resume_code(from_stage: str) -> str:
    raw = str(from_stage or "").strip()
    if raw == "01":
        raise ValueError("请直接运行 whole-lca")
    if raw in RESUME_CODES:
        return raw
    m = re.match(r"^(\d{2})", raw)
    if m and m.group(1) in RESUME_CODES:
        return m.group(1)
    raise ValueError(f"无效的 from_stage：{from_stage!r}")


def stage_id_from_code(code: str) -> str:
    key = normalize_resume_code(code)
    return RESUME_CODES[key]


def stage_num(stage_id: str) -> int:
    m = re.match(r"^(\d{2})", str(stage_id or ""))
    return int(m.group(1)) if m else 0


def floor_stage_id(code: str) -> str | None:
    if "-" in code:
        return code
    try:
        return stage_id_from_code(code)
    except ValueError:
        return RESUME_CODES.get(code)
