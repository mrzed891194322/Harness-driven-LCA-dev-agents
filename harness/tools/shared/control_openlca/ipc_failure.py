"""Transport timeout / unresponsive IPC: probe, events, diagnostics, agent contract."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from .connection import close_ipc_client, connection_error_kind, probe_ipc
from .diagnostics import capture_openlca_timeout_diagnostics, resolve_run_diagnostics_dir
from .guard import mark_uncertain
from .run_events import append_run_event, utc_now_iso
from .timeout_policy import health_probe_sec

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)

NON_RETRYABLE_KIND = "openlca_unresponsive"
AGENT_STOP_MESSAGE = (
    "openLCA IPC timed out and appears unresponsive. Do not retry import, "
    "cleanup, or calculate; stop and submit_handoff with failed status."
)


def _probe_timeout() -> tuple[float, float]:
    probe = health_probe_sec()
    return (min(1.0, probe / 3), probe)


def health_probe_responsive(host: str, port: int) -> tuple[bool, str]:
    client = None
    try:
        client = probe_ipc(host, port, timeout=_probe_timeout())
        return True, "ok"
    except Exception as exc:
        return False, connection_error_kind(exc)
    finally:
        close_ipc_client(client)


def build_non_retryable_error(
    *,
    message: str,
    entity: dict[str, Any] | None = None,
    diagnostics_path: str | None = None,
    probe: str | None = None,
) -> dict[str, Any]:
    detail = message
    if entity:
        detail = (
            f"{message} "
            f"(path={entity.get('path')}, type={entity.get('entity_type')}, "
            f"name={entity.get('name')}, id={entity.get('id')})"
        )
    errors = [
        {
            "kind": NON_RETRYABLE_KIND,
            "message": detail[:2000],
            "retryable": False,
            "agent_action": "stop_and_submit_failed",
        }
    ]
    payload: dict[str, Any] = {
        "ok": False,
        "status": "failed",
        "errors": [detail],
        "structured_errors": errors,
        "error_kind": NON_RETRYABLE_KIND,
        "retryable": False,
        "agent_action": "stop_and_submit_failed",
        "agent_message": AGENT_STOP_MESSAGE,
    }
    if diagnostics_path:
        payload["diagnostics_path"] = diagnostics_path
    if probe:
        payload["health_probe"] = probe
    if entity:
        payload["timed_out_entity"] = entity
    return payload


def on_ipc_transport_failure(
    host: str,
    port: int,
    exc: BaseException,
    *,
    operation: str,
    entity: dict[str, Any] | None = None,
    run_id: str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Mark IPC uncertain, probe health, emit event + diagnostics when unresponsive."""
    mark_uncertain()
    responsive, probe_kind = health_probe_responsive(host, port)
    root = project_root or PROJECT_ROOT
    resolved_run = (run_id or os.getenv("LCA_RUN_ID", "")).strip()
    diag_path: str | None = None
    run_dir = resolve_run_diagnostics_dir(root, resolved_run or None)
    context = {
        "operation": operation,
        "exception": str(exc)[:500],
        "entity": entity,
        "probe": probe_kind,
        "responsive": responsive,
    }
    if run_dir is not None:
        captured = capture_openlca_timeout_diagnostics(
            run_dir, host=host, port=port, context=context
        )
        if captured is not None:
            diag_path = str(captured)

    if not responsive and resolved_run and not resolved_run.startswith("standalone-"):
        try:
            append_run_event(
                root,
                resolved_run,
                {
                    "kind": NON_RETRYABLE_KIND,
                    "ts": utc_now_iso(),
                    "summary": "openLCA IPC unresponsive after timeout",
                    "endpoint": f"{host}:{port}",
                    "operation": operation,
                    "entity": entity,
                    "probe": probe_kind,
                    "diagnostics_path": diag_path,
                },
            )
        except Exception:
            pass

    message = str(exc)
    if isinstance(exc, requests.Timeout):
        message = f"IPC read timeout during {operation}: {exc}"
    return build_non_retryable_error(
        message=message,
        entity=entity,
        diagnostics_path=diag_path,
        probe=probe_kind if not responsive else None,
    )
