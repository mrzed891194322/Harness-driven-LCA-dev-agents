"""Shared path constants and script-local import helpers for the test suite."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
GUI_ROOT = SRC_ROOT / "GUI"
WORKFLOWS = PROJECT_ROOT / "harness" / "workflows"


@contextmanager
def local_script_packages(package_dir: Path):
    """Import a script-local ``utils`` without leaking it into the shared pytest session."""
    sys.path.insert(0, str(package_dir))
    saved = {
        key: sys.modules[key]
        for key in list(sys.modules)
        if key == "utils" or key.startswith("utils.")
    }
    for key in saved:
        del sys.modules[key]
    try:
        yield
    finally:
        for key in list(sys.modules):
            if key == "utils" or key.startswith("utils."):
                del sys.modules[key]
        sys.modules.update(saved)
        if sys.path and sys.path[0] == str(package_dir):
            sys.path.pop(0)
