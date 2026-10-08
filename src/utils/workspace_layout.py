"""Canonical workspace subdirectory names (shared by core, GUI, and harness tools)."""

from __future__ import annotations

from pathlib import Path

RECORDS_DIRNAME = "records"


def records_root(workspace_root: Path) -> Path:
    return workspace_root / RECORDS_DIRNAME
