from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SyncResult:
    ok: bool
    target: str = "noop"
    message: str = "skipped"
    details: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)


def sync_files(kind: str, **_: Any) -> SyncResult:
    """No-op sync for legacy console helpers used in tests."""
    return SyncResult(ok=True, target=kind, message="ok")
