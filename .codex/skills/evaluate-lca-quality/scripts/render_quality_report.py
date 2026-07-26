#!/usr/bin/env python3
"""Skill entry point for deterministic quality-score validation and rendering."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
QUALITY_SCRIPT_ROOT = (
    PROJECT_ROOT
    / ".codex"
    / "specs"
    / "lca-quality-evaluation"
    / "references"
    / "scripts"
)
if str(QUALITY_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUALITY_SCRIPT_ROOT))

from cli import main


if __name__ == "__main__":
    raise SystemExit(main())
