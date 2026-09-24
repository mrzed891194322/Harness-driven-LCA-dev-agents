"""Host Action runtime: Core-facing JSON stdin/stdout subprocess calls."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.runtime.context import RunContext
from core.runtime.tool_runtime import _handoff_path_for_context
from core.workflow.config.models import HostActionSpec


@dataclass
class HostActionResult:
    ok: bool
    status: str
    summary: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_summary(self, check_id: str) -> dict[str, object]:
        return {
            "check_id": check_id,
            "status": self.status,
            "summary": self.summary,
        }


def build_host_context(
    run_ctx: RunContext,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Pure-data context JSON for Host Action / MCP wire (no Python DTO sharing)."""
    root = project_root or run_ctx.project_root
    return {
        "schema_version": 1,
        "run_id": run_ctx.run_id,
        "stage": run_ctx.stage_id,
        "assignment": run_ctx.assignment_id,
        "attempt": run_ctx.attempt,
        "role": run_ctx.role,
        "workspace": str(run_ctx.workspace_root),
        "project_root": str(root),
        "metadata": dict(run_ctx.metadata),
        "handoff_path": _handoff_path_for_context(run_ctx),
    }


def normalize_host_action_result(payload: Any) -> HostActionResult:
    if not isinstance(payload, dict):
        return HostActionResult(
            ok=False,
            status="failed",
            summary="Host Action result was not an object",
            errors=["Host Action result was not an object"],
        )
    if "ok" not in payload and "status" not in payload:
        return HostActionResult(
            ok=False,
            status="failed",
            summary="Host Action result missing ok/status",
            errors=["Host Action result missing ok/status"],
            raw=dict(payload),
        )
    errors = payload.get("errors") or []
    if not isinstance(errors, list):
        errors = [str(errors)]
    warnings = payload.get("warnings") or []
    if not isinstance(warnings, list):
        warnings = [str(warnings)]
    ok = payload.get("ok")
    if ok is None:
        status = str(payload.get("status") or "").lower()
        ok = status in {"passed", "success", "ok", "completed"}
    else:
        ok = bool(ok)
    status = str(payload.get("status") or ("passed" if ok else "failed"))
    summary = str(payload.get("summary") or "").strip()
    if not summary and errors:
        summary = "; ".join(str(item) for item in errors[:5])
    details = payload.get("details")
    if not isinstance(details, dict):
        details = {}
    return HostActionResult(
        ok=ok,
        status=status,
        summary=summary,
        errors=[str(item) for item in errors],
        warnings=[str(item) for item in warnings],
        details=dict(details),
        raw=dict(payload),
    )


def run_host_action(
    action: HostActionSpec,
    *,
    run_ctx: RunContext,
    project_root: Path,
    arguments: dict[str, Any] | None = None,
    timeout_sec: float | None = None,
) -> HostActionResult:
    """Spawn Host Action once with JSON stdin; parse single JSON stdout object."""
    declared = int(action.tool_timeout_sec)
    if declared <= 0:
        return HostActionResult(
            ok=False,
            status="failed",
            summary=f"tool_timeout_sec must be positive: {action.action_id}",
            errors=[f"tool_timeout_sec must be positive: {action.action_id}"],
        )
    deadline = float(timeout_sec if timeout_sec is not None else declared)
    payload = {
        "context": build_host_context(run_ctx, project_root=project_root),
        "arguments": dict(arguments or {}),
    }
    env = {
        key: os.environ[key]
        for key in ("HOME", "PATH", "LANG", "LC_ALL", "VIRTUAL_ENV")
        if key in os.environ
    }
    env.update({str(k): str(v) for k, v in action.env.items()})
    env.setdefault("PYTHONPATH", str(project_root))
    try:
        completed = subprocess.run(
            [action.command, *action.args],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=env,
            timeout=deadline,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return HostActionResult(
            ok=False,
            status="failed",
            summary=f"Host Action timed out: {exc}",
            errors=[f"Host Action timed out: {exc}"],
        )
    except OSError as exc:
        return HostActionResult(
            ok=False,
            status="failed",
            summary=str(exc),
            errors=[str(exc)],
        )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:500]
        return HostActionResult(
            ok=False,
            status="failed",
            summary=(
                f"Host Action exited {completed.returncode}"
                + (f": {detail}" if detail else "")
            ),
            errors=[
                f"Host Action exited {completed.returncode}"
                + (f": {detail}" if detail else "")
            ],
        )
    text = (completed.stdout or "").strip()
    if not text:
        return HostActionResult(
            ok=False,
            status="failed",
            summary="Host Action produced empty stdout",
            errors=["Host Action produced empty stdout"],
        )
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return HostActionResult(
            ok=False,
            status="failed",
            summary=f"Host Action stdout was not JSON: {exc}",
            errors=[f"Host Action stdout was not JSON: {exc}"],
        )
    return normalize_host_action_result(parsed)
