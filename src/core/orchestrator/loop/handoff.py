"""Handoff JSON protocol."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.runtime.tool_runtime import write_json_atomic

SCHEMA_VERSION = 1
WRITER_ROLES = frozenset({"executor", "reviser"})
WRITER_STATUSES = {"ok", "failed", "blocked"}
REVIEWER_STATUSES = {"passed", "failed"}


def handoff_not_found_error(path: Path) -> FileNotFoundError:
    return FileNotFoundError(
        f"{path}: handoff 文件不存在（当前角色须在运行上下文 handoff_path 写入 JSON 交卷）"
    )


def _path_ref(value: Any, *, field: str, path: Path) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        ref_path = value.get("path")
        if isinstance(ref_path, str) and ref_path.strip():
            return ref_path
    raise ValueError(f"{path}: {field} 必须是路径字符串")


def handoff_path(workspace_root: Path, stage_id: str, role: str, attempt: int) -> Path:
    return workspace_root / "memory" / "handoffs" / f"{stage_id}-{role}-{attempt}.json"


def validate_handoff_payload(
    payload: dict[str, Any],
    *,
    path: Path,
    role: str,
    stage: str,
    attempt: int,
) -> dict[str, Any]:
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
        if field in payload:
            payload[field] = _path_ref(payload[field], field=field, path=path)
    return payload


def write_handoff_file(
    path: Path,
    payload: dict[str, Any],
    *,
    role: str,
    stage: str,
    attempt: int,
) -> dict[str, Any]:
    validated = validate_handoff_payload(
        dict(payload), path=path, role=role, stage=stage, attempt=attempt
    )
    write_json_atomic(path, validated)
    return validated


def read_handoff(
    path: Path,
    *,
    role: str,
    stage: str,
    attempt: int,
) -> dict[str, Any]:
    if not path.is_file():
        raise handoff_not_found_error(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: handoff 必须是 JSON 对象")
    return validate_handoff_payload(
        payload, path=path, role=role, stage=stage, attempt=attempt
    )


def review_note_path(workspace_root: Path, stage_id: str, attempt: int) -> Path:
    return workspace_root / "memory" / "reviews" / f"{stage_id}-{attempt}.md"


def write_review_note(
    path: Path,
    handoff: dict[str, Any],
    *,
    system_status: str | None = None,
    system_reason: str = "",
) -> None:
    """Write the auditable review outcome for this attempt.

    ``system_status`` records host acceptance after reviewer handoff:
    accepted | invalidated | hook_failed | failed (or None for plain reviewer failed).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    status = handoff.get("status")
    reason = handoff.get("status_reason") or ""
    fixes = handoff.get("fix_instructions") or ""
    lines = [
        f"# {handoff.get('stage')} 审查 {handoff.get('attempt')}",
        "",
        f"Reviewer 结论：{status}",
        "",
    ]
    if system_status is not None:
        lines.extend(
            [
                f"系统验收：{system_status}",
                "",
            ]
        )
        if system_reason:
            lines.extend(["原因：", "", str(system_reason), ""])
    lines.extend(
        [
            "## 摘要",
            "",
            str(reason),
            "",
        ]
    )
    if fixes:
        lines.extend(["## 要改什么", "", str(fixes), ""])
    path.write_text("\n".join(lines), encoding="utf-8")
