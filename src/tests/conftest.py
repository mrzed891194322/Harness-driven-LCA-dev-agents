"""Shared path constants for the test suite."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
GUI_ROOT = SRC_ROOT / "gui"
WORKFLOWS = PROJECT_ROOT / "harness"
