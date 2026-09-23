# ruff: noqa: E402
"""MCP local artifact tools; no database or network operations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from mcp.server import MCPServer
from mcp_types import ToolAnnotations

from core.runtime.context import RunContext
from core.workflow.execution.handoff import (
    handoff_path,
    write_handoff_file,
)
from harness.tools.lca_artifacts import checks, report
from harness.tools.lca_artifacts.handoff import validate as validate_handoff_payload
from harness.tools.lca_artifacts.store import (
    Context,
    bind_context_argv,
    invoke,
)

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


@mcp.tool(
    description="Check current-stage inventory, mapping or report; persist an audit without changing reviewed artifacts.",
    annotations=AUDIT,
    structured_output=True,
)
def validate_artifacts(
    profile: Literal["inventory", "mapping", "report"],
) -> dict[str, Any]:
    def execute() -> dict[str, Any]:
        result = checks.validate(Context.environment(), profile)
        ok = bool(result.get("ok"))
        errors = list(result.get("errors") or [])
        return {
            **result,
            "ok": ok,
            "status": "passed" if ok else "failed",
            "summary": str(result.get("summary") or "")
            or ("; ".join(str(e) for e in errors[:5]) if errors else ""),
            "errors": [str(e) for e in errors],
            "warnings": list(result.get("warnings") or []),
        }

    return invoke(
        "validate_artifacts",
        execute,
        arguments={"profile": profile},
    )


@mcp.tool(
    description="Read checks and invalidate changed dependencies; no openLCA calls.",
    annotations=AUDIT,
    structured_output=True,
)
def get_validation_state(
    profile: Literal["inventory", "mapping", "report"],
) -> dict[str, Any]:
    def execute():
        value = checks.validation_state(Context.environment(), profile)
        return {
            "ok": True,
            "checks": [{k: v for k, v in value.items() if k != "inputs"}],
        }

    return invoke("get_validation_state", execute, arguments={"profile": profile})


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
        path = handoff_path(ctx.workspace, ctx.stage, ctx.role, ctx.attempt)
        body: dict[str, Any] = {
            "schema_version": 1,
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
        run_ctx = RunContext(
            ctx.project,
            ctx.workspace,
            ctx.run_id,
            ctx.stage,
            assignment,
            ctx.attempt,
            ctx.role,
            dict(ctx.metadata or {}),
        )
        validated = write_handoff_file(
            path,
            body,
            role=ctx.role,
            stage=ctx.stage,
            attempt=ctx.attempt,
        )
        validate_handoff_payload(run_ctx, validated)
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
    description="Record mapping acceptance after reviewer passed (host lifecycle action).",
    annotations=WRITE,
    structured_output=True,
)
def record_acceptance(
    profile: Literal["inventory", "mapping", "report"] = "mapping",
) -> dict[str, Any]:
    def execute() -> dict[str, Any]:
        if profile != "mapping":
            raise ValueError(
                f"record_acceptance requires profile='mapping', got {profile!r}"
            )
        ctx = Context.environment()
        checks.record_acceptance(ctx, acceptance_key=checks.ACCEPTANCE_MODEL)
        return {
            "ok": True,
            "status": "passed",
            "summary": "acceptance recorded",
            "errors": [],
            "warnings": [],
        }

    return invoke("record_acceptance", execute, arguments={"profile": profile})


@mcp.tool(
    description="Validate optional handoff business fields (e.g. rework_scope).",
    annotations=AUDIT,
    structured_output=True,
)
def validate_handoff(handoff: dict[str, Any] | None = None) -> dict[str, Any]:
    def execute() -> dict[str, Any]:
        ctx = Context.environment()
        payload = dict(handoff or {})
        assignment = ctx.assignment or f"{ctx.stage}-{ctx.role}"
        run_ctx = RunContext(
            ctx.project,
            ctx.workspace,
            ctx.run_id,
            ctx.stage,
            assignment,
            ctx.attempt,
            ctx.role,
            dict(ctx.metadata or {}),
        )
        try:
            validate_handoff_payload(run_ctx, payload)
        except ValueError as exc:
            return {
                "ok": False,
                "status": "failed",
                "summary": str(exc),
                "errors": [str(exc)],
                "warnings": [],
            }
        return {
            "ok": True,
            "status": "passed",
            "summary": "handoff ok",
            "errors": [],
            "warnings": [],
        }

    return invoke("validate_handoff", execute, arguments={"handoff": handoff})


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
