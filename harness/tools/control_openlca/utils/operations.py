"""V2 import receipts: explicit requests, durable preflights, no blind retries."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from . import workflow as w
from .connection import (
    close_ipc_client,
    create_ipc_client,
    is_transport_error,
)
from .guard import mark_uncertain


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value
    ):
        raise ValueError("invalid run/request/operation identifier")
    return value


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def journal_root(path):
    root = Path(path).resolve()
    if root.exists() and any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("operation journal must not contain symbolic links")
    return root


def request_identity(host, port, run_id, database_name, category, lci_dir):
    root = Path(lci_dir).resolve()
    files = {
        str(p.relative_to(root)): w.sha256_file(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    return {
        "run_id": identifier(run_id),
        "endpoint": w.build_endpoint(host, port),
        "database_name": w._active_database_label(
            w.build_endpoint(host, port), database_name
        )[0],
        "category": category,
        "lci_dir": str(root),
        "lci_content": w.stable_hash(files),
    }


def preflight(
    host,
    port,
    lci_dir,
    target_category,
    database_name,
    *,
    run_id,
    operation_dir,
    client=None,
):
    identifier(run_id)
    operation_dir = journal_root(operation_dir)
    result, _, _ = w._inspect_import(
        host, port, lci_dir, target_category, database_name, client
    )
    result["preflight_id"] = str(uuid.uuid4())
    result["identity"] = request_identity(
        host, port, run_id, database_name, target_category, lci_dir
    )
    result["database_identity_verified"] = False
    if result["ok"]:
        w._write_json_atomic(
            Path(operation_dir) / "preflights" / f"{result['preflight_id']}.json",
            result,
        )
    return result


def get_operation(operation_dir, *, run_id, request_id=None, operation_id=None):
    identifier(run_id)
    root = journal_root(operation_dir)
    if request_id and operation_id:
        raise ValueError("supply request_id or operation_id, not both")
    if request_id:
        index = (
            root / "requests" / identifier(run_id) / f"{identifier(request_id)}.json"
        )
    elif operation_id:
        index = None
    else:
        index = root / "current.json"
    try:
        if index is not None:
            if not index.exists():
                return {"status": "not_found", "errors": []}
            resolved_operation_id = read(index).get("operation_id")
            if resolved_operation_id is None:
                return {"status": "not_found", "errors": []}
            operation_id = str(resolved_operation_id)
        if operation_id is None:
            return {"status": "not_found", "errors": []}
        report = read(root / "operations" / f"{identifier(operation_id)}.json")
        if report["identity"]["run_id"] != run_id:
            return {"status": "not_found", "errors": []}
        if report["status"] == "running":
            try:
                os.kill(int(report["owner_pid"]), 0)
            except (OSError, KeyError, ValueError):
                report = {
                    **report,
                    "status": "indeterminate",
                    "observed_status": "running",
                }
        return report
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {
            "status": "indeterminate",
            "errors": [f"unreadable operation journal: {exc}"],
        }


def reconcile_cleanup(operation_dir, host, port, category):
    """An explicitly completed cleanup clears the active pointer, not old receipts."""
    root = journal_root(operation_dir)
    current_path = root / "current.json"
    if not current_path.exists():
        return
    current = read(current_path)
    operation_id = current.get("operation_id")
    path = (
        root / "operations" / f"{identifier(operation_id)}.json"
        if operation_id
        else None
    )
    if path is None or not path.exists():
        identity = {
            "endpoint": current.get("endpoint"),
            "category": current.get("target_category"),
        }
    else:
        identity = read(path)["identity"]
    if (
        identity.get("endpoint") != w.build_endpoint(host, port)
        or identity.get("category") != category
    ):
        return
    w._write_json_atomic(
        root / "reconciliations" / f"{uuid.uuid4().hex}.json",
        {
            "previous": current,
            "reason": "explicit cleanup completed",
            "at": w.utc_now(),
            "endpoint": identity["endpoint"],
            "category": category,
        },
    )
    current_path.unlink()


def import_request(
    host,
    port,
    lci_dir,
    target_category,
    database_name,
    *,
    run_id,
    request_id,
    preflight_id,
    operation_dir,
    client=None,
):
    identifier(request_id)
    identifier(preflight_id)
    root = journal_root(operation_dir)
    identity = request_identity(
        host, port, run_id, database_name, target_category, lci_dir
    )
    existing = get_operation(root, run_id=run_id, request_id=request_id)
    if existing["status"] != "not_found":
        if (
            existing.get("identity") != identity
            or existing.get("preflight_id") != preflight_id
        ):
            return {
                "status": "rejected",
                "errors": ["request_identity_mismatch"],
                "execution_mode": "not_executed",
            }
        return {
            **existing,
            "execution_mode": "reused",
            "source_operation_id": existing["operation_id"],
            "reuse_reason": "same request; journal returned without database writes",
        }
    saved = read(root / "preflights" / f"{preflight_id}.json")
    if saved.get("identity") != identity:
        return {
            "status": "rejected",
            "errors": ["preflight_identity_mismatch"],
            "execution_mode": "not_executed",
        }
    # One preflight authorizes one request, including after partial failure.
    consumed = root / "consumed" / f"{preflight_id}.json"
    if consumed.exists():
        return {
            "status": "rejected",
            "errors": ["preflight_already_consumed"],
            "execution_mode": "not_executed",
        }
    if (root / "current.json").exists():
        current_id = read(root / "current.json").get("operation_id")
        if not current_id:
            return {
                "status": "indeterminate",
                "errors": ["legacy journal must be resolved before v2 import"],
            }
        current = read(root / "operations" / f"{identifier(current_id)}.json")
        if current["status"] in {
            "running",
            "indeterminate",
            "partial_failure",
            "failed",
        }:
            return {
                "status": "indeterminate",
                "errors": ["previous import requires reconciliation"],
                "operation_id": current_id,
            }
    run_scope = root / "scopes" / f"{identifier(run_id)}.json"
    scope = {
        k: identity[k]
        for k in ("run_id", "endpoint", "database_name", "category", "lci_dir")
    }
    if run_scope.exists() and read(run_scope) != scope:
        return {"status": "rejected", "errors": ["run_scope_changed"]}
    ipc = client or create_ipc_client(host, port)
    report = None
    started = time.monotonic()
    try:
        current, inventory, targets = w._inspect_import(
            host, port, lci_dir, target_category, database_name, ipc
        )
        if not current["ok"] or current["preflight_hash"] != saved["preflight_hash"]:
            return {
                "status": "rejected",
                "errors": ["preflight_stale", *current["errors"]],
                "execution_mode": "not_executed",
            }
        # Recheck local bytes after IPC reads, before the first write.
        if (
            request_identity(
                host, port, run_id, database_name, target_category, lci_dir
            )
            != identity
        ):
            return {"status": "rejected", "errors": ["lci_changed_during_preflight"]}
        operation_id = str(uuid.uuid4())
        report = {
            "schema_version": 2,
            "status": "running",
            "operation_id": operation_id,
            "owner_pid": os.getpid(),
            "request_id": request_id,
            "preflight_id": preflight_id,
            "identity": identity,
            "execution_mode": "executed",
            "started_at": w.utc_now(),
            "requested_at": w.utc_now(),
            "success_count": 0,
            "failed_count": 0,
            "deleted_count": 0,
            "entities": [],
            "errors": [],
        }
        path = root / "operations" / f"{operation_id}.json"
        w._write_json_atomic(path, report)
        # Persist receipts before touching the database. Incomplete receipts fail closed.
        w._write_json_atomic(
            root / "requests" / run_id / f"{request_id}.json",
            {"operation_id": operation_id},
        )
        w._write_json_atomic(root / "current.json", {"operation_id": operation_id})
        w._write_json_atomic(consumed, {"operation_id": operation_id})
        w._write_json_atomic(run_scope, scope)

        def progress(records, imported, failed, deleted, errors):
            report.update(
                entities=list(records),
                success_count=imported,
                failed_count=failed,
                deleted_count=deleted,
                errors=list(errors),
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            w._write_json_atomic(path, report)

        records, imported, failed, deleted, errors = w._execute_import(
            ipc, inventory, targets, target_category, on_progress=progress
        )
        progress(records, imported, failed, deleted, errors)
        report.update(
            status="success"
            if not failed and imported == len(inventory)
            else "partial_failure",
            ended_at=w.utc_now(),
        )
        w._write_json_atomic(path, report)
        return report
    except Exception as exc:
        if report is not None:
            report.update(status="indeterminate", errors=[*report["errors"], str(exc)])
            w._write_json_atomic(path, report)
        if is_transport_error(exc):
            mark_uncertain()
        raise
    finally:
        if client is None:
            close_ipc_client(ipc)
