#!/usr/bin/env python
"""Workflow CLI — thin wrapper over services.workflow / orchestrator."""

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

from services.workflow import run_workflow


def main(argv: list[str] | None = None) -> int:
    return run_workflow(argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
