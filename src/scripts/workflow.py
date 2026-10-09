#!/usr/bin/env python
"""Internal orchestrator entry: forward argv to the core workflow engine (``--workflow`` required).

Used by the control-panel backend / tests as a subprocess; not a user-facing control surface.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
for _p in (_ROOT / "src", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.core.workflow.main import main as orchestrator_main  # noqa: E402

PROJECT_ROOT = _ROOT


def main(argv: list[str] | None = None) -> int:
    return orchestrator_main(argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
