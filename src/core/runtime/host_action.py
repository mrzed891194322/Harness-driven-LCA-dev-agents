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


def _protocol_failure(
    message: str, *, raw: dict[str, Any] | None = None
) -> HostActionResult:
    return HostActionResult(
        ok=False,
        status="failed",
        summary=message,
        errors=[message],
        raw=dict(raw or {}),
    )


def normalize_host_action_result(payload: Any) -> HostActionResult:
    """Fail-closed Host Action result protocol (schema_version 1)."""
    if not isinstance(payload, dict):
        return _protocol_failure("Host Action result was not an object")
    if payload.get("schema_version") != _HOST_ACTION_SCHEMA_VERSION:
        return _protocol_failure(
            f"Host Action schema_version must be {_HOST_ACTION_SCHEMA_VERSION}, "
            f"got {payload.get('schema_version')!r}",
            raw=payload,
        )
    if "ok" not in payload or "status" not in payload:
        return _protocol_failure(
            "Host Action result missing ok/status",
            raw=payload,
        )
    ok = payload["ok"]
    if not isinstance(ok, bool):
        return _protocol_failure("Host Action ok must be a boolean", raw=payload)
    status = payload["status"]
    if not isinstance(status, str) or status not in _ALLOWED_STATUS:
        return _protocol_failure(
            f"Host Action status must be one of {sorted(_ALLOWED_STATUS)}, "
            f"got {status!r}",
            raw=payload,
        )
    if ok and status != "passed":
        return _protocol_failure(
            f"Host Action ok/status mismatch: ok={ok!r} status={status!r}",
            raw=payload,
        )
    if not ok and status != "failed":
        return _protocol_failure(
            f"Host Action ok/status mismatch: ok={ok!r} status={status!r}",
            raw=payload,
        )
    summary = payload.get("summary")
    if not isinstance(summary, str):
        return _protocol_failure("Host Action summary must be a string", raw=payload)
    errors = payload.get("errors")
    if not isinstance(errors, list) or any(
        not isinstance(item, str) for item in errors
    ):
        return _protocol_failure(
            "Host Action errors must be a list of strings", raw=payload
        )
    warnings = payload.get("warnings")
    if not isinstance(warnings, list) or any(
        not isinstance(item, str) for item in warnings
    ):
        return _protocol_failure(
            "Host Action warnings must be a list of strings",
            raw=payload,
        )
    details = payload.get("details", {})
    if not isinstance(details, dict):
        return _protocol_failure("Host Action details must be an object", raw=payload)
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
    """Spawn Host Action once with JSON stdin; parse single JSON stdout object."""
    declared = int(action.tool_timeout_sec)
    if declared <= 0:
        return _protocol_failure(
            f"tool_timeout_sec must be positive: {action.action_id}"
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
        return _protocol_failure(f"Host Action timed out: {exc}")
    except OSError as exc:
        return _protocol_failure(str(exc))
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:500]
        return _protocol_failure(
            f"Host Action exited {completed.returncode}"
            + (f": {detail}" if detail else "")
        )
    text = (completed.stdout or "").strip()
    if not text:
        return _protocol_failure("Host Action produced empty stdout")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return _protocol_failure(f"Host Action stdout was not JSON: {exc}")
    return normalize_host_action_result(parsed)
