"""Shared path bootstrap for src/test modules."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
GUI_ROOT = SRC_ROOT / "GUI"

# The GUI keeps script-compatible top-level imports so that
# ``python src/GUI/main.py`` remains a supported entry point.
for import_root in (SRC_ROOT, GUI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


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
