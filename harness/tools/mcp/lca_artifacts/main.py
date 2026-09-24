# ruff: noqa: E402
"""MCP local artifact tools; no database or network operations."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from mcp_types import ToolAnnotations

from harness.tools.mcp.control_openlca.utils.workflow import _write_json_atomic
from harness.tools.shared.lca_artifacts import checks, report
from harness.tools.shared.lca_artifacts.handoff import (
    validate as validate_handoff_payload,
)
from harness.tools.shared.lca_artifacts.path_safety import require_relative_path
from harness.tools.shared.lca_artifacts.store import (
    Context,
    bind_context_argv,
    invoke,
)
from mcp.server import MCPServer

mcp = MCPServer(
    "lca-artifacts",
    instructions="Offline checks produce evidence, not stage approval. Artifact paths are relative to workspace.",
)
AUDIT = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)

_SCHEMA_VERSION = 1
_WRITER_ROLES = frozenset({"executor", "reviser"})
_WRITER_STATUSES = {"ok", "failed", "blocked"}
_REVIEWER_STATUSES = {"passed", "failed"}


def _resolve_handoff_path(ctx: Context) -> Path:
    raw = str(ctx.handoff_path or os.getenv("LCA_HANDOFF_PATH") or "").strip()
    if not raw:
        raise ValueError("handoff_path missing from host context")
    if Path(raw).is_absolute():
        path = Path(raw)
    else:
        require_relative_path(raw, label="handoff_path")
        path = ctx.workspace / raw
    return ctx.safe(path)


def _validate_core_handoff(
    payload: dict[str, Any],
    *,
    path: Path,
    role: str,
    stage: str,
    attempt: int,
) -> dict[str, Any]:
    """Mirror core handoff protocol fields without importing core."""
    if int(payload.get("schema_version") or 0) != _SCHEMA_VERSION:
        raise ValueError(f"{path}: schema_version must be {_SCHEMA_VERSION}")
    if payload.get("role") != role:
        raise ValueError(f"{path}: role mismatch")
    if payload.get("stage") != stage:
        raise ValueError(f"{path}: stage mismatch")
    if int(payload.get("attempt") or 0) != attempt:
        raise ValueError(f"{path}: attempt mismatch")
    status = str(payload.get("status") or "")
    allowed = _WRITER_STATUSES if role in _WRITER_ROLES else _REVIEWER_STATUSES
    if status not in allowed:
        raise ValueError(f"{path}: invalid status {status!r}")
    if not str(payload.get("status_reason") or "").strip():
        raise ValueError(f"{path}: status_reason must not be empty")
    if role == "reviewer" and status == "failed":
        if not str(payload.get("fix_instructions") or "").strip():
            raise ValueError(f"{path}: failed review requires fix_instructions")
    payload.setdefault("fix_instructions", "")
    payload.setdefault("artifacts", [])
    if not isinstance(payload["artifacts"], list):
        raise ValueError(f"{path}: artifacts must be a list")
    if any(not isinstance(item, str) for item in payload["artifacts"]):
        raise ValueError(f"{path}: artifacts must be path strings")
    if not isinstance(payload["fix_instructions"], str):
        raise ValueError(f"{path}: fix_instructions must be a string")
    return payload


@mcp.tool(
    description="Determine whether same-run stage-04 retry can reuse raw evidence without any IPC calls.",
    annotations=AUDIT,
    structured_output=True,
)
def get_rework_status() -> dict[str, Any]:
    return invoke(
        "get_rework_status", lambda: checks.reuse_status(Context.environment())
    )


@mcp.tool(
    description="Submit the current assignment handoff JSON; host picks path and validates schema.",
    annotations=WRITE,
    structured_output=True,
)
def submit_handoff(
    status: str,
    status_reason: str,
    fix_instructions: str = "",
    artifacts: list[str] | None = None,
    checks_ref: str | None = None,
    evidence_manifest_ref: str | None = None,
    rework_scope: str = "none",
) -> dict[str, Any]:
    def execute() -> dict[str, Any]:
        ctx = Context.environment()
        path = _resolve_handoff_path(ctx)
        body: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "role": ctx.role,
            "stage": ctx.stage,
            "attempt": ctx.attempt,
            "status": status,
            "status_reason": status_reason,
            "fix_instructions": fix_instructions,
            "artifacts": list(artifacts or []),
            "rework_scope": rework_scope,
        }
        if checks_ref is not None:
            body["checks_ref"] = checks_ref
        if evidence_manifest_ref is not None:
            body["evidence_manifest_ref"] = evidence_manifest_ref
        assignment = ctx.assignment or f"{ctx.stage}-{ctx.role}"
        validated = _validate_core_handoff(
            body,
            path=path,
            role=ctx.role,
            stage=ctx.stage,
            attempt=ctx.attempt,
        )
        validate_handoff_payload(validated, label=assignment)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, validated)
        rel = path.relative_to(ctx.workspace)
        return {"ok": True, "path": rel.as_posix()}

    return invoke(
        "submit_handoff",
        execute,
        arguments={
            "status": status,
            "status_reason": status_reason,
            "artifacts": artifacts,
        },
    )


@mcp.tool(
    description="Writer only: replace marked inventory/mapping/LCIA tables while retaining narrative.",
    annotations=WRITE,
    structured_output=True,
)
def render_report_tables() -> dict[str, Any]:
    return invoke("render_report_tables", lambda: report.render(Context.environment()))


@mcp.tool(
    description="Read a bounded UTF-8 slice of a checksummed workspace artifact (offset in characters).",
    annotations=AUDIT,
    structured_output=True,
)
def read_artifact(
    path: str,
    sha256: str,
    offset: int = 0,
    limit: int = 2000,
    json_pointer: str | None = None,
) -> dict[str, Any]:
    def execute():
        if isinstance(offset, bool) or offset < 0 or not 1 <= limit <= 4000:
            raise ValueError("offset >= 0 and limit 1..4000 required")
        ctx = Context.environment()
        text = ctx.resolve_ref({"path": path, "sha256": sha256}).read_text(
            encoding="utf-8"
        )
        if json_pointer is not None:
            if json_pointer and not json_pointer.startswith("/"):
                raise ValueError("json_pointer must be empty or begin with /")
            selected = json.loads(text)
            for token in json_pointer.split("/")[1:] if json_pointer else []:
                key = token.replace("~1", "/").replace("~0", "~")
                selected = (
                    selected[int(key)] if isinstance(selected, list) else selected[key]
                )
            text = json.dumps(selected, ensure_ascii=False, indent=2)
        chunk = text[offset : offset + limit]
        return {
            "ok": True,
            "items": [{"text": chunk}],
            "has_more": offset + len(chunk) < len(text),
            "next_offset": offset + len(chunk)
            if offset + len(chunk) < len(text)
            else None,
        }

    return invoke(
        "read_artifact",
        execute,
        arguments={
            "path": path,
            "offset": offset,
            "limit": limit,
            "json_pointer": json_pointer,
        },
    )


if __name__ == "__main__":
    bind_context_argv()
    mcp.run()
