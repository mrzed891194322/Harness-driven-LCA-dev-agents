"""Read-only BOM claims checks. Warn-oriented for MCP; narrow hard set for host gate.

This module never deletes or rewrites claims.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# types.md blacklist (unit short forms / common spellings). Host hard-gates these only.
BLACKLIST_UNITS: frozenset[str] = frozenset({
    "h", "hr", "hrs", "hour", "hours",
    "°c", "°f", "celsius", "fahrenheit",
    "degc", "degf", "deg c", "deg f",
})

_HOUR_RE = re.compile(r"^(?:man\s*)?(?:h|hr|hrs|hours?)$", re.I)
_TEMP_RE = re.compile(r"^(?:°\s*[cf]|deg(?:ree)?s?\s*[cf]|[cf]elsius|fahrenheit)$", re.I)


def _norm_unit(unit: Any) -> str:
    if unit is None:
        return ""
    return str(unit).strip().lower().replace("℃", "°c").replace("℉", "°f")


def _is_blacklist_unit(unit: Any) -> bool:
    u = _norm_unit(unit)
    if not u:
        return False
    if u in BLACKLIST_UNITS:
        return True
    if _HOUR_RE.match(u) or _TEMP_RE.match(u):
        return True
    return False


def check_claims_payload(data: Any) -> dict[str, Any]:
    """Return ``{ok, warnings, hard_errors, claim_count}`` without mutating ``data``.

    ``hard_errors`` = narrow host gate (blacklist units only).
    ``warnings`` = soft guidance (empty volume, missing fields, etc.). MCP surfaces both;
    host gate uses only ``hard_errors``.
    """
    warnings: list[str] = []
    hard_errors: list[str] = []

    if not isinstance(data, dict):
        hard_errors.append("claims 根必须是 object")
        return {"ok": False, "warnings": warnings, "hard_errors": hard_errors, "claim_count": 0}

    claims = data.get("claims")
    if not isinstance(claims, list):
        hard_errors.append("claims 必须是数组")
        return {"ok": False, "warnings": warnings, "hard_errors": hard_errors, "claim_count": 0}

    abstained = bool(data.get("abstained"))
    if abstained and claims:
        warnings.append("abstained=true 却仍有 claims；确认是否应清空或取消弃权")
    if not abstained and not claims:
        warnings.append(
            "claims 为空且未 abstained：有原文依据时勿空交；仅完全无数字可答才可空 claims"
        )

    for i, claim in enumerate(claims):
        where = f"claims[{i}]"
        if not isinstance(claim, dict):
            hard_errors.append(f"{where}: 必须是 object")
            continue
        cid = claim.get("claim_id") or where
        unit = claim.get("unit")
        if _is_blacklist_unit(unit):
            hard_errors.append(
                f"{cid}: 黑名单单位 {unit!r}（工时 h/hr/hour 或温度 °C/°F）；"
                "题面未问时删除该条，勿整卷清空"
            )
        if claim.get("value") is None and not (claim.get("text") or "").strip():
            warnings.append(f"{cid}: 缺 value/text，确认是否为有效声明")
        if unit is not None and isinstance(unit, str) and len(unit) > 24:
            warnings.append(
                f"{cid}: unit 过长（{len(unit)} 字），应交短符号（见 units.md），勿交原文短语"
            )
        if not (claim.get("evidence") or "").strip() and not abstained:
            warnings.append(f"{cid}: 缺 evidence；自检时按证据关系局部删，勿无依据多报")

    ok = not hard_errors
    return {
        "ok": ok,
        "warnings": warnings,
        "hard_errors": hard_errors,
        "claim_count": len(claims) if isinstance(claims, list) else 0,
        "message": (
            "只告警/列错，未改写 claims（禁止自动删）。"
            "仅对确认违规（黑名单单位等）手动删条；吃不准则保留。"
        ),
    }


def check_claims_file(path: Path) -> dict[str, Any]:
    """Load JSON at ``path`` and run :func:`check_claims_payload` (read-only)."""
    if not path.is_file():
        return {
            "ok": False,
            "warnings": [],
            "hard_errors": [f"文件不存在：{path}"],
            "claim_count": 0,
            "message": "claims 文件缺失；先写出再 check。未改写任何文件。",
        }
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "ok": False,
            "warnings": [],
            "hard_errors": [f"无法读取：{exc}"],
            "claim_count": 0,
            "message": "读失败；未改写任何文件。",
        }
    if not text.strip():
        return {
            "ok": False,
            "warnings": [],
            "hard_errors": ["文件为空"],
            "claim_count": 0,
            "message": "空文件；未改写。",
        }
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "warnings": [],
            "hard_errors": [f"JSON 无法解析：{exc}"],
            "claim_count": 0,
            "message": "解析失败；未改写任何文件。",
        }
    return check_claims_payload(data)


def hard_errors_for_host(path: Path) -> list[str]:
    """Narrow host gate: blacklist-unit hard_errors only (plus unreadable file)."""
    result = check_claims_file(path)
    return list(result.get("hard_errors") or [])
