#!/usr/bin/env python
"""Workspace / openLCA clean CLI (thin argparse wrapper)."""

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

from services.workspace import cli_main

if __name__ == "__main__":
    cli_main()
