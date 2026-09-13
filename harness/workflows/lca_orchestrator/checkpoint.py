"""Local SQLite checkpointer for LangGraph."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def checkpoint_path(workspace_root: Path) -> Path:
    return workspace_root / "memory" / "orchestrator.sqlite"


def open_checkpointer(workspace_root: Path) -> tuple[sqlite3.Connection, SqliteSaver]:
    path = checkpoint_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    return conn, SqliteSaver(conn)
