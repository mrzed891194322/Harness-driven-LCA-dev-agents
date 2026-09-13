"""Handoff JSON protocol."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
WRITER_ROLES = frozenset({"executor", "reviser"})
WRITER_STATUSES = {"ok", "failed", "blocked"}
REVIEWER_STATUSES = {"passed", "failed"}


def handoff_path(workspace_root: Path, stage_id: str, role: str, attempt: int) -> Path:
    return workspace_root / "memory" / "handoffs" / f"{stage_id}-{role}-{attempt}.json"


def read_handoff(
    path: Path,
    *,
    role: str,
    stage: str,
    attempt: int,
) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: handoff 必须是 JSON 对象")
    if int(payload.get("schema_version") or 0) != SCHEMA_VERSION:
        raise ValueError(f"{path}: schema_version 必须为 {SCHEMA_VERSION}")
    if payload.get("role") != role:
        raise ValueError(f"{path}: role 不匹配")
    if payload.get("stage") != stage:
        raise ValueError(f"{path}: stage 不匹配")
    if int(payload.get("attempt") or 0) != attempt:
        raise ValueError(f"{path}: attempt 不匹配")
    status = str(payload.get("status") or "")
    allowed = WRITER_STATUSES if role in WRITER_ROLES else REVIEWER_STATUSES
    if status not in allowed:
        raise ValueError(f"{path}: 非法 status {status!r}")
    reason = str(payload.get("status_reason") or "").strip()
    if not reason:
        raise ValueError(f"{path}: status_reason 不能为空")
    if role == "reviewer" and status == "failed":
        if not str(payload.get("fix_instructions") or "").strip():
            raise ValueError(f"{path}: 审查失败必须给出 fix_instructions")
    payload.setdefault("fix_instructions", "")
    payload.setdefault("artifacts", [])
    if not isinstance(payload["artifacts"], list):
        raise ValueError(f"{path}: artifacts 必须是列表")
    if any(not isinstance(item, str) for item in payload["artifacts"]):
        raise ValueError(f"{path}: artifacts 必须是路径字符串列表")
    if not isinstance(payload["fix_instructions"], str):
        raise ValueError(f"{path}: fix_instructions 必须是字符串")
    for field in ("checks_ref", "evidence_manifest_ref"):
        if field in payload and not isinstance(payload[field], str):
            raise ValueError(f"{path}: {field} 必须是路径字符串")
    if payload.get("rework_scope", "none") not in {
        "none",
        "report_only",
        "calculation_changed",
        "model_changed",
    }:
        raise ValueError(f"{path}: invalid rework_scope")
    return payload


def review_note_path(workspace_root: Path, stage_id: str, attempt: int) -> Path:
    return workspace_root / "memory" / "reviews" / f"{stage_id}-{attempt}.md"


def write_review_note(path: Path, handoff: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status = handoff.get("status")
    reason = handoff.get("status_reason") or ""
    fixes = handoff.get("fix_instructions") or ""
    lines = [
        f"# {handoff.get('stage')} 审查 {handoff.get('attempt')}",
        "",
        f"结论：{status}",
        "",
        "## 摘要",
        "",
        str(reason),
        "",
    ]
    if fixes:
        lines.extend(["## 要改什么", "", str(fixes), ""])
    path.write_text("\n".join(lines), encoding="utf-8")
