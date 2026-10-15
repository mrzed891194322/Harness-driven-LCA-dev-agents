"""Detect orchestrator / launch threads that died while a run is still marked running."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.agents.activity import activity_log_path, append_activity
from backend.core.workflow.persistence.checkpoint import checkpoint_path, open_store
from backend.core.workflow.persistence.heartbeat import (
    clear_heartbeat,
    heartbeat_age_sec,
    heartbeat_stale_sec,
    read_heartbeat,
)
from backend.core.workflow.persistence.manifest import manifest_path, write_manifest
from backend.settings import run_root

REASON_BACKEND_RESTART = "后端重启导致编排中断"
REASON_HEARTBEAT_TIMEOUT = "心跳超时"

_TERMINAL = frozenset({"completed", "failed", "interrupted"})


def reconcile_project(project_root: Path) -> bool:
    """Reconcile launch state and the workspace manifest. Returns True if anything changed."""
    workspace_root = project_root / "workspace"
    changed = reconcile_launch_state(project_root)
    changed = reconcile_workspace_run(project_root, workspace_root) or changed
    return changed


def reconcile_launch_state(project_root: Path) -> bool:
    from backend.services.workflow_launch import launcher

    with launcher._lock:
        if launcher.status != "running":
            return False
        thread = launcher._thread
        if thread is not None and thread.is_alive():
            return False
        launcher.status = "interrupted"
        launcher.reason = REASON_BACKEND_RESTART
    launcher._note(REASON_BACKEND_RESTART)
    return True


def reconcile_workspace_run(project_root: Path, workspace_root: Path) -> bool:
    from backend.services.workflow_launch import launch_snapshot

    snap = launch_snapshot()
    if snap.get("status") == "running":
        return False

    path = manifest_path(workspace_root)
    if not path.is_file():
        return False
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(manifest, dict):
        return False
    status = str(manifest.get("status") or "")
    if status in _TERMINAL:
        return False
    if status != "running":
        return False

    run_id = str(manifest.get("run_id") or "").strip()
    if not run_id:
        return False

    if orchestrator_lock_held(workspace_root):
        return False

    heartbeat = read_heartbeat(workspace_root)
    if heartbeat is not None:
        age = heartbeat_age_sec(heartbeat)
        pid = _coerce_pid(heartbeat.get("pid"))
        stale_after = heartbeat_stale_sec()
        if age is not None and age <= stale_after and pid is not None and pid_alive(pid):
            return False
        if age is not None and age > stale_after:
            return _mark_interrupted(
                project_root,
                workspace_root,
                run_id,
                manifest,
                REASON_HEARTBEAT_TIMEOUT,
            )

    heartbeat_pid = _coerce_pid(heartbeat.get("pid")) if heartbeat else None
    if heartbeat_pid is not None and pid_alive(heartbeat_pid):
        return False

    return _mark_interrupted(
        project_root,
        workspace_root,
        run_id,
        manifest,
        REASON_BACKEND_RESTART,
    )


def orchestrator_lock_held(workspace_root: Path) -> bool:
    """True when a live process holds ``runs/_run/orchestrator.lock`` (non-blocking probe)."""
    path = run_root(workspace_root) / "orchestrator.lock"
    if not path.is_file():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        import msvcrt

        with path.open("a+b") as stream:
            if path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return True
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        return False

    import fcntl

    with path.open("a+b") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    return False


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def workflow_status_for_run(workspace_root: Path, run_id: str) -> str | None:
    path = manifest_path(workspace_root)
    if path.is_file():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
        if isinstance(manifest, dict) and str(manifest.get("run_id") or "") == run_id:
            return str(manifest.get("status") or "") or None
    db = checkpoint_path(workspace_root)
    if not db.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0.2)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute(
            "SELECT state_json FROM workflow_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if not row:
        return None
    try:
        state = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    if isinstance(state, dict):
        return str(state.get("status") or "") or None
    return None


def _mark_interrupted(
    project_root: Path,
    workspace_root: Path,
    run_id: str,
    manifest: dict[str, Any],
    reason: str,
) -> bool:
    stage = manifest.get("current_stage")
    attempt = manifest.get("attempt")
    write_manifest(
        workspace_root,
        status="interrupted",
        current_stage=stage if isinstance(stage, str) else None,
        status_reason=reason,
        run_id=run_id,
        attempt=attempt if isinstance(attempt, int) else None,
    )
    _update_checkpoint(workspace_root, run_id, reason)
    _emit_interrupted(project_root, run_id, reason, manifest)
    clear_heartbeat(workspace_root)
    return True


def _update_checkpoint(workspace_root: Path, run_id: str, reason: str) -> None:
    db = checkpoint_path(workspace_root)
    if not db.is_file():
        return
    try:
        with open_store(workspace_root) as store:
            state = store.load(run_id)
            if not state or str(state.get("status") or "") in _TERMINAL:
                return
            if str(state.get("status") or "") != "running":
                return
            state.update(
                status="interrupted",
                status_reason=reason,
                in_flight=False,
                next_action="done",
            )
            store.save(state, event="run_interrupted", action="")
    except (OSError, sqlite3.Error):
        pass


def _emit_interrupted(
    project_root: Path,
    run_id: str,
    reason: str,
    manifest: dict[str, Any],
) -> None:
    try:
        path = activity_log_path(project_root, run_id)
    except ValueError:
        return
    record = {
        "source": "backend",
        "kind": "run_interrupted",
        "run_id": run_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "summary": reason,
        "stage": manifest.get("current_stage"),
        "attempt": manifest.get("attempt"),
    }
    try:
        append_activity(path, record)
    except OSError:
        pass


def _coerce_pid(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None
