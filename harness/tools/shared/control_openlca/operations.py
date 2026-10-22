"""Import journal: ``preflights/<id>.json`` + ``operations/<id>.json``, nothing else.

Each operation file carries its own receipts (``request_ids``, ``preflight_ids``, ``touched_at``,
``cleared``); the "current" operation is the newest uncleared one by ``touched_at``.
No blind retries; one preflight authorizes one request.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from .importer import (
    _active_database_label,
    _execute_import,
    _inspect_import,
    find_uncertain_leftover_entities,
)
from .lci_inventory import (
    _write_json_atomic,
    build_entity_plan,
    sha256_file,
    stable_hash,
    utc_now,
)
from .connection import (
    build_endpoint,
)
from .connection import (
    close_ipc_client,
    create_ipc_client,
    is_transport_error,
)
from .guard import prior_uncertain_marker
from .ipc_failure import (
    NON_RETRYABLE_KIND,
    as_import_recoverable,
    on_ipc_transport_failure,
)

IDENTITY_SCOPE_KEYS = (
    "run_id",
    "endpoint",
    "database_name",
    "category",
    "lci_dir",
)


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


def load_operations(root: Path) -> list[dict]:
    """Every operation report; an unreadable file fails closed as indeterminate."""
    out: list[dict] = []
    ops = root / "operations"
    if not ops.is_dir():
        return out
    for path in sorted(ops.glob("*.json")):
        try:
            out.append(read(path))
        except (OSError, ValueError) as exc:
            out.append({"operation_id": path.stem, "status": "indeterminate", "identity": {},
                        "errors": [f"unreadable operation journal: {exc}"], "touched_at": "~"})
    return out


def current_operation(root: Path) -> dict | None:
    live = [r for r in load_operations(root) if not r.get("cleared")]
    return max(live, key=lambda r: str(r.get("touched_at") or r.get("started_at") or "")) if live else None


def preflight_consumed(root: Path, preflight_id: str) -> bool:
    return any(preflight_id in (r.get("preflight_ids") or [r.get("preflight_id")]) for r in load_operations(root))


def _add_receipt(report: dict, request_id: str, preflight_id: str) -> None:
    report["request_ids"] = [*(report.get("request_ids") or []), request_id]
    report["preflight_ids"] = [*(report.get("preflight_ids") or []), preflight_id]
    report["touched_at"] = utc_now()


def identity_scope(identity: dict) -> dict:
    return {key: identity[key] for key in IDENTITY_SCOPE_KEYS if key in identity}


def compare_identity_scope(expected: dict, actual: dict) -> list[str]:
    errors: list[str] = []
    for key in IDENTITY_SCOPE_KEYS:
        if expected.get(key) != actual.get(key):
            errors.append(
                "resume_scope_mismatch: "
                f"field={key} expected={expected.get(key)!r} got={actual.get(key)!r}"
            )
    return errors


def run_owned_entity_ids(operation_dir, run_id, scope: dict) -> set[str]:
    """Entity ids written by prior operations in this run with the same import scope."""
    root = journal_root(operation_dir)
    owned: set[str] = set()
    operations_dir = root / "operations"
    if not operations_dir.is_dir():
        return owned
    for path in sorted(operations_dir.glob("*.json")):
        try:
            report = read(path)
        except (OSError, ValueError, TypeError, KeyError):
            continue
        ident = report.get("identity") or {}
        if ident.get("run_id") != run_id:
            continue
        if identity_scope(ident) != scope:
            continue
        for entry in report.get("entity_plan") or []:
            entity_id = entry.get("id")
            if entity_id:
                owned.add(str(entity_id))
        for entry in report.get("entities") or []:
            if entry.get("action") != "create_or_update":
                continue
            entity_id = entry.get("id")
            if entity_id:
                owned.add(str(entity_id))
    return owned


def merge_entity_plan_for_content_change(
    previous_plan: list[dict],
    inventory: list[dict],
) -> tuple[list[dict], list[str]]:
    """Reuse done entities when content_hash matches; re-import when it changed."""
    previous_by_id = {str(entry["id"]): dict(entry) for entry in previous_plan}
    merged: list[dict] = []
    changed_entities: list[str] = []
    for item in inventory:
        entry = build_entity_plan([item])[0]
        prior = previous_by_id.get(str(item["id"]))
        if prior is None:
            merged.append(entry)
            continue
        if (
            prior.get("status") == "done"
            and prior.get("content_hash") == entry.get("content_hash")
        ):
            entry["status"] = "done"
        elif prior.get("content_hash") != entry.get("content_hash"):
            changed_entities.append(str(item["id"]))
        elif prior.get("status") in {"failed", "uncertain", "pending"}:
            entry["status"] = prior.get("status", "pending")
        merged.append(entry)
    return merged, changed_entities


def request_identity(host, port, run_id, database_name, category, lci_dir):
    root = Path(lci_dir).resolve()
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError(
                f"LCI directory must not contain symbolic links: "
                f"{p.relative_to(root).as_posix()}"
            )
        if not p.is_file():
            continue
        try:
            resolved = p.resolve()
        except OSError as exc:
            raise ValueError(f"cannot resolve LCI path {p}: {exc}") from exc
        if resolved != root and root not in resolved.parents:
            raise ValueError(
                f"LCI path escapes LCI root: {p.relative_to(root).as_posix()}"
            )
        files[str(p.relative_to(root))] = sha256_file(p)
    return {
        "run_id": identifier(run_id),
        "endpoint": build_endpoint(host, port),
        "database_name": _active_database_label(
            build_endpoint(host, port), database_name
        )[0],
        "category": category,
        "lci_dir": str(root),
        "lci_content": stable_hash(files),
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
    result, _, _ = _inspect_import(
        host, port, lci_dir, target_category, database_name, client
    )
    result["preflight_id"] = str(uuid.uuid4())
    result["identity"] = request_identity(
        host, port, run_id, database_name, target_category, lci_dir
    )
    result["database_identity_verified"] = False
    if result["ok"]:
        _write_json_atomic(
            Path(operation_dir) / "preflights" / f"{result['preflight_id']}.json",
            result,
        )
    return result


def get_operation(operation_dir, *, run_id, request_id=None, operation_id=None):
    identifier(run_id)
    root = journal_root(operation_dir)
    if request_id and operation_id:
        raise ValueError("supply request_id or operation_id, not both")
    try:
        if request_id:
            identifier(request_id)
            hits = [r for r in load_operations(root)
                    if (r.get("identity") or {}).get("run_id") == run_id
                    and request_id in (r.get("request_ids") or [])]
            if not hits:
                return {"status": "not_found", "errors": []}
            operation_id = str(hits[0]["operation_id"])
        elif not operation_id:
            cur = current_operation(root)
            if cur is None:
                return {"status": "not_found", "errors": []}
            operation_id = str(cur["operation_id"])
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
    """A completed cleanup clears the current operation (marked in its own file, receipts kept)."""
    root = journal_root(operation_dir)
    current = current_operation(root)
    if current is None or not current.get("operation_id"):
        return
    identity = current.get("identity") or {}
    if identity.get("endpoint") != build_endpoint(host, port) or identity.get("category") != category:
        return
    path = root / "operations" / f"{identifier(str(current['operation_id']))}.json"
    if not path.exists():
        return
    report = read(path)
    report["cleared"] = {"reason": "explicit cleanup completed", "at": utc_now(),
                         "endpoint": identity["endpoint"], "category": category}
    _write_json_atomic(path, report)


def _finalize_import_report(
    report: dict,
    path,
    inventory,
    records,
    imported,
    failed,
    deleted,
    errors,
    started: float,
) -> dict:
    report.update(
        entities=list(records),
        success_count=imported,
        failed_count=failed,
        deleted_count=deleted,
        errors=list(errors),
        duration_ms=round((time.monotonic() - started) * 1000),
    )
    planned = len(inventory)
    done = sum(
        1 for entry in report.get("entity_plan") or [] if entry.get("status") == "done"
    )
    if not failed and done >= planned:
        status = "success"
    elif failed:
        status = "partial_failure"
    elif done < planned:
        status = "partial_failure"
    else:
        status = "success"
    if imported == 0 and failed and done == 0 and planned <= 1:
        status = "failed"
    report.update(status=status, ended_at=utc_now())
    if status == "partial_failure" and not report.get("error_kind"):
        report.update(
            agent_action="reconcile_and_resume",
            agent_message=(
                "Import incomplete. Read get_import_operation(operation_id=...), then "
                "call import_lci(resume_operation_id=...) with a new request_id and "
                "preflight_id; do not start a fresh import."
            ),
        )
    _write_json_atomic(path, report)
    return report


def resume_import_request(
    host,
    port,
    lci_dir,
    target_category,
    database_name,
    *,
    run_id,
    request_id,
    preflight_id,
    operation_id,
    operation_dir,
    client=None,
):
    identifier(request_id)
    identifier(preflight_id)
    identifier(operation_id)
    root = journal_root(operation_dir)
    identity = request_identity(
        host, port, run_id, database_name, target_category, lci_dir
    )
    path = root / "operations" / f"{identifier(operation_id)}.json"
    if not path.exists():
        return {
            "status": "rejected",
            "errors": ["operation_not_found"],
            "execution_mode": "not_executed",
        }
    report = read(path)
    scope = identity_scope(identity)
    scope_errors = compare_identity_scope(scope, identity_scope(report.get("identity") or {}))
    if scope_errors:
        return {
            "status": "rejected",
            "errors": scope_errors,
            "execution_mode": "not_executed",
        }
    content_matches = (report.get("identity") or {}).get("lci_content") == identity.get(
        "lci_content"
    )
    if report.get("status") == "success" and content_matches:
        return {
            **report,
            "execution_mode": "reused",
            "source_operation_id": operation_id,
            "reuse_reason": "operation already succeeded with identical LCI content",
        }
    if report.get("status") not in {
        "partial_failure",
        "failed",
        "indeterminate",
        "success",
    }:
        return {
            "status": "rejected",
            "errors": [f"operation_not_resumable:{report.get('status')}"],
            "execution_mode": "not_executed",
        }
    saved = read(root / "preflights" / f"{preflight_id}.json")
    preflight_scope_errors = compare_identity_scope(
        scope, identity_scope(saved.get("identity") or {})
    )
    if preflight_scope_errors:
        return {
            "status": "rejected",
            "errors": ["preflight_scope_mismatch", *preflight_scope_errors],
            "execution_mode": "not_executed",
        }
    if preflight_consumed(root, preflight_id):
        return {
            "status": "rejected",
            "errors": ["preflight_already_consumed"],
            "execution_mode": "not_executed",
        }
    ipc = client or create_ipc_client(host, port)
    started = time.monotonic()
    try:
        current, inventory, targets = _inspect_import(
            host, port, lci_dir, target_category, database_name, ipc
        )
        if not current["ok"] or current["preflight_hash"] != saved["preflight_hash"]:
            return {
                "status": "rejected",
                "errors": ["preflight_stale", *current["errors"]],
                "execution_mode": "not_executed",
            }
        previous_plan = list(report.get("entity_plan") or [])
        if content_matches:
            plan = list(previous_plan or build_entity_plan(inventory))
        else:
            plan, changed_entities = merge_entity_plan_for_content_change(
                previous_plan, inventory
            )
            report["changed_entities"] = changed_entities
        report.update(
            status="running",
            owner_pid=os.getpid(),
            request_id=request_id,
            preflight_id=preflight_id,
            cleared=None,
            execution_mode="resumed",
            resumed_at=utc_now(),
            identity=identity,
            entity_plan=plan,
            errors=[],
        )
        _add_receipt(report, request_id, preflight_id)
        _write_json_atomic(path, report)

        def progress(records, imported, failed, deleted, errors):
            report.update(
                entities=list(records),
                entity_plan=plan,
                success_count=imported,
                failed_count=failed,
                deleted_count=deleted,
                errors=list(errors),
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            _write_json_atomic(path, report)

        records, imported, failed, deleted, errors = _execute_import(
            ipc,
            inventory,
            targets,
            target_category,
            on_progress=progress,
            host=host,
            port=port,
            resume=True,
            entity_plan=plan,
        )
        return _finalize_import_report(
            report,
            path,
            inventory,
            records,
            imported,
            failed,
            deleted,
            errors,
            started,
        )
    except Exception as exc:
        report.update(status="indeterminate", errors=[*report.get("errors", []), str(exc)])
        _write_json_atomic(path, report)
        if is_transport_error(exc):
            failure = on_ipc_transport_failure(
                host,
                port,
                exc,
                operation="resume_import_request",
                run_id=run_id,
            )
            failure = as_import_recoverable(failure)
            return {**report, **failure}
        raise
    finally:
        if client is None:
            close_ipc_client(ipc)


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
    resume_operation_id: str | None = None,
):
    if resume_operation_id:
        return resume_import_request(
            host,
            port,
            lci_dir,
            target_category,
            database_name,
            run_id=run_id,
            request_id=request_id,
            preflight_id=preflight_id,
            operation_id=resume_operation_id,
            operation_dir=operation_dir,
            client=client,
        )
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
    scope = identity_scope(identity)
    preflight_scope_errors = compare_identity_scope(
        scope, identity_scope(saved.get("identity") or {})
    )
    if preflight_scope_errors:
        return {
            "status": "rejected",
            "errors": ["preflight_scope_mismatch", *preflight_scope_errors],
            "execution_mode": "not_executed",
        }
    # One preflight authorizes one request, including after partial failure.
    if preflight_consumed(root, preflight_id):
        return {
            "status": "rejected",
            "errors": ["preflight_already_consumed"],
            "execution_mode": "not_executed",
        }
    open_op = current_operation(root)
    if open_op is not None:
        current_id = open_op.get("operation_id")
        current = open_op
        if current["status"] in {"running", "indeterminate"}:
            return {
                "status": "indeterminate",
                "errors": ["previous import still running or indeterminate"],
                "operation_id": current_id,
            }
        if current["status"] in {"partial_failure", "failed"}:
            return {
                "status": "indeterminate",
                "errors": ["previous import requires reconciliation"],
                "operation_id": current_id,
                "agent_action": "reconcile_and_resume",
                "agent_message": (
                    "Read get_import_operation(operation_id=...), then call "
                    "import_lci(resume_operation_id=...) with a new request_id and "
                    "preflight_id. Do not start a fresh import while this operation is open."
                ),
            }
    scope = identity_scope(identity)
    if any(identity_scope(r.get("identity") or {}) != scope
           for r in load_operations(root) if (r.get("identity") or {}).get("run_id") == run_id):
        return {"status": "rejected", "errors": ["run_scope_changed"]}
    ipc = client or create_ipc_client(host, port)
    report = None
    started = time.monotonic()
    try:
        current, inventory, targets = _inspect_import(
            host, port, lci_dir, target_category, database_name, ipc
        )
        if not current["ok"] or current["preflight_hash"] != saved["preflight_hash"]:
            return {
                "status": "rejected",
                "errors": ["preflight_stale", *current["errors"]],
                "execution_mode": "not_executed",
            }
        if prior_uncertain_marker(host, port):
            leftovers = find_uncertain_leftover_entities(
                ipc, inventory, target_category
            )
            run_owned = run_owned_entity_ids(root, run_id, scope)
            foreign_leftovers = [
                item
                for item in leftovers
                if str(item.get("id") or "") not in run_owned
            ]
            if foreign_leftovers:
                return {
                    "status": "rejected",
                    "errors": [
                        "uncertain_ipc_leftover_entities: database still contains "
                        "entities matching this import after a prior timeout; "
                        "manual openLCA check/restart required before retry",
                        *[
                            f"leftover {item['entity_type']} {item['name']} "
                            f"({item['id']}) from {item['path']}"
                            for item in foreign_leftovers
                        ],
                    ],
                    "leftover_entities": foreign_leftovers,
                    "execution_mode": "not_executed",
                    "retryable": False,
                    "error_kind": NON_RETRYABLE_KIND,
                    "agent_action": "stop_and_submit_failed",
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
        superseded_operation_id = None
        changed_entities: list[str] = []
        prior = current_operation(root)
        if prior is not None:
            prior_id = prior.get("operation_id")
            if prior_id:
                prior_report = prior
                prior_identity = prior_report.get("identity") or {}
                if (
                    identity_scope(prior_identity) == scope
                    and prior_report.get("status") == "success"
                    and prior_identity.get("lci_content") != identity.get("lci_content")
                ):
                    superseded_operation_id = str(prior_id)
                    changed_entities = [
                        item["id"]
                        for item in inventory
                        if any(
                            entry.get("id") == item["id"]
                            and entry.get("content_hash") != item.get("sha256", "")
                            for entry in prior_report.get("entity_plan") or []
                        )
                    ]
        entity_plan = build_entity_plan(inventory)
        report = {
            "schema_version": 2,
            "status": "running",
            "operation_id": operation_id,
            "owner_pid": os.getpid(),
            "request_id": request_id,
            "preflight_id": preflight_id,
            "identity": identity,
            "execution_mode": "executed",
            "superseded_operation_id": superseded_operation_id,
            "changed_entities": changed_entities or None,
            "started_at": utc_now(),
            "requested_at": utc_now(),
            "success_count": 0,
            "failed_count": 0,
            "deleted_count": 0,
            "entities": [],
            "entity_plan": entity_plan,
            "errors": [],
        }
        path = root / "operations" / f"{operation_id}.json"
        # The receipt lives in the operation file, written before touching the database.
        _add_receipt(report, request_id, preflight_id)
        _write_json_atomic(path, report)

        def progress(records, imported, failed, deleted, errors):
            report.update(
                entities=list(records),
                entity_plan=entity_plan,
                success_count=imported,
                failed_count=failed,
                deleted_count=deleted,
                errors=list(errors),
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            _write_json_atomic(path, report)

        records, imported, failed, deleted, errors = _execute_import(
            ipc,
            inventory,
            targets,
            target_category,
            on_progress=progress,
            host=host,
            port=port,
            entity_plan=entity_plan,
        )
        return _finalize_import_report(
            report,
            path,
            inventory,
            records,
            imported,
            failed,
            deleted,
            errors,
            started,
        )
    except Exception as exc:
        if report is not None:
            report.update(status="indeterminate", errors=[*report["errors"], str(exc)])
            _write_json_atomic(path, report)
        if is_transport_error(exc):
            failure = on_ipc_transport_failure(
                host,
                port,
                exc,
                operation="import_request",
                run_id=run_id,
            )
            failure = as_import_recoverable(failure)
            return {**report, **failure} if report is not None else failure
        raise
    finally:
        if client is None:
            close_ipc_client(ipc)
