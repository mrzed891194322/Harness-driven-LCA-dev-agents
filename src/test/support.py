"""Shared path bootstrap for src/test modules."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
GUI_ROOT = SRC_ROOT / "GUI"

# The GUI keeps script-compatible top-level imports so that
# ``python src/GUI/main.py`` remains a supported entry point.
for import_root in (SRC_ROOT, GUI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))
