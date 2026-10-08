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

_HOST_ACTION_SCHEMA_VERSION = 1
_ALLOWED_STATUS = frozenset({"passed", "failed"})
_RESULT_KEYS = frozenset(
    {"schema_version", "ok", "status", "summary", "errors", "warnings", "details"}
)
_REQUEST_KEYS = frozenset({"schema_version", "context", "arguments"})
_CONTEXT_KEYS = frozenset(
    {
        "run_id",
        "stage",
        "assignment",
        "attempt",
        "role",
        "workspace",
        "project_root",
        "metadata",
        "handoff_path",
    }
)


class HostActionError(RuntimeError):
    """Base: Host Action infrastructure or wire-protocol failure (not business)."""


class HostActionExecutionError(HostActionError):
    """Spawn/timeout/nonzero exit — process could not complete normally."""


class HostActionProtocolError(HostActionError):
    """Stdout is not a valid Host Action result envelope."""


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
    """Pure-data context object nested under the Host Action request envelope."""
    root = project_root or run_ctx.project_root
    return {
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


def build_host_request(
    run_ctx: RunContext,
    *,
    project_root: Path | None = None,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full stdin JSON envelope for Host Action subprocesses."""
    return {
        "schema_version": _HOST_ACTION_SCHEMA_VERSION,
        "context": build_host_context(run_ctx, project_root=project_root),
        "arguments": dict(arguments or {}),
    }


def normalize_host_action_result(payload: Any) -> HostActionResult:
    """Parse a valid business result; raise HostActionProtocolError on wire faults."""
    if not isinstance(payload, dict):
        raise HostActionProtocolError("Host Action result was not an object")
    unknown = set(payload) - _RESULT_KEYS
    if unknown:
        raise HostActionProtocolError(
            f"Host Action result has unknown fields: {sorted(unknown)}"
        )
    if payload.get("schema_version") != _HOST_ACTION_SCHEMA_VERSION:
        raise HostActionProtocolError(
            f"Host Action schema_version must be {_HOST_ACTION_SCHEMA_VERSION}, "
            f"got {payload.get('schema_version')!r}"
        )
    if "ok" not in payload or "status" not in payload:
        raise HostActionProtocolError("Host Action result missing ok/status")
    ok = payload["ok"]
    if not isinstance(ok, bool):
        raise HostActionProtocolError("Host Action ok must be a boolean")
    status = payload["status"]
    if not isinstance(status, str) or status not in _ALLOWED_STATUS:
        raise HostActionProtocolError(
            f"Host Action status must be one of {sorted(_ALLOWED_STATUS)}, "
            f"got {status!r}"
        )
    if ok and status != "passed":
        raise HostActionProtocolError(
            f"Host Action ok/status mismatch: ok={ok!r} status={status!r}"
        )
    if not ok and status != "failed":
        raise HostActionProtocolError(
            f"Host Action ok/status mismatch: ok={ok!r} status={status!r}"
        )
    summary = payload.get("summary")
    if not isinstance(summary, str):
        raise HostActionProtocolError("Host Action summary must be a string")
    errors = payload.get("errors")
    if not isinstance(errors, list) or any(
        not isinstance(item, str) for item in errors
    ):
        raise HostActionProtocolError("Host Action errors must be a list of strings")
    warnings = payload.get("warnings")
    if not isinstance(warnings, list) or any(
        not isinstance(item, str) for item in warnings
    ):
        raise HostActionProtocolError("Host Action warnings must be a list of strings")
    details = payload.get("details", {})
    if not isinstance(details, dict):
        raise HostActionProtocolError("Host Action details must be an object")
    if ok and errors:
        raise HostActionProtocolError(
            "Host Action ok=true cannot include non-empty errors"
        )
    return HostActionResult(
        ok=ok,
        status=status,
        summary=summary,
        errors=list(errors),
        warnings=list(warnings),
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
    """Spawn Host Action; return business result or raise HostActionError."""
    declared = int(action.timeout_sec)
    if declared <= 0:
        raise HostActionProtocolError(
            f"timeout_sec must be positive: {action.action_id}"
        )
    deadline = float(timeout_sec if timeout_sec is not None else declared)
    payload = build_host_request(
        run_ctx, project_root=project_root, arguments=arguments
    )
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
        raise HostActionExecutionError(f"Host Action timed out: {exc}") from exc
    except OSError as exc:
        raise HostActionExecutionError(str(exc)) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:500]
        raise HostActionExecutionError(
            f"Host Action exited {completed.returncode}"
            + (f": {detail}" if detail else "")
        )
    text = (completed.stdout or "").strip()
    if not text:
        raise HostActionProtocolError("Host Action produced empty stdout")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HostActionProtocolError(
            f"Host Action stdout was not JSON: {exc}"
        ) from exc
    return normalize_host_action_result(parsed)
