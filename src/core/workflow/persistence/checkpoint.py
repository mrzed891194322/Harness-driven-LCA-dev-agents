"""SQLite snapshots, compact action events, and a workspace process lock."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from ..execution.runner import WorkflowState


def checkpoint_path(workspace_root: Path) -> Path:
    return workspace_root / "memory" / "orchestrator.sqlite"


class WorkspaceBusy(RuntimeError):
    pass


@contextmanager
def workspace_lock(workspace_root: Path) -> Iterator[None]:
    """Fail immediately if another orchestrator owns this workspace."""
    path = workspace_root / "memory" / "orchestrator.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            if path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise WorkspaceBusy(f"workspace busy: {workspace_root}") from exc
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise WorkspaceBusy(f"workspace busy: {workspace_root}") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    # Keep the lock file: unlinking it can let processes lock different inodes.


class CheckpointStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        # Separate tables leave legacy LangGraph checkpoints untouched.
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                run_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workflow_events (
                id INTEGER PRIMARY KEY,
                run_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                event TEXT NOT NULL,
                action TEXT NOT NULL,
                details_json TEXT NOT NULL
            );
        """)

    def load(self, run_id: str) -> WorkflowState | None:
        row = self.conn.execute(
            "SELECT state_json FROM workflow_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return cast("WorkflowState", json.loads(row[0])) if row else None

    def save(
        self,
        state: WorkflowState,
        *,
        event: str,
        action: str = "",
        context: WorkflowState | None = None,
    ) -> None:
        """Commit the snapshot and its event together, then release the transaction."""
        observed = context if context is not None else state
        details = {
            key: observed.get(key)
            for key in (
                "current_stage",
                "current_assignment",
                "attempt",
                "protocol_repairs",
            )
        }
        details.update(
            status=state.get("status"), status_reason=state.get("status_reason")
        )
        payload = json.dumps(state, ensure_ascii=False)
        with self.conn:
            self.conn.execute(
                "INSERT INTO workflow_runs(run_id, state_json) VALUES (?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET state_json = excluded.state_json",
                (state["run_id"], payload),
            )
            self.conn.execute(
                "INSERT INTO workflow_events(run_id, event, action, details_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    state["run_id"],
                    event,
                    action,
                    json.dumps(details, ensure_ascii=False),
                ),
            )


@contextmanager
def open_store(workspace_root: Path) -> Iterator[CheckpointStore]:
    path = checkpoint_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        yield CheckpointStore(conn)
