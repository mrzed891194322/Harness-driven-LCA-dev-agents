"""Optional host hooks registered outside ``core`` (see ``orchestrator_wiring``)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

BeforeOpenLcaWrite = Callable[..., None]

_before_openlca_write: BeforeOpenLcaWrite | None = None


def set_before_openlca_write(handler: BeforeOpenLcaWrite | None) -> None:
    global _before_openlca_write
    _before_openlca_write = handler


def get_before_openlca_write() -> BeforeOpenLcaWrite | None:
    return _before_openlca_write
