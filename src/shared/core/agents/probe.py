"""Diagnostic probes for Pi SDK runtime (no PATH CLI workers)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .inspect import check, inspect
from .providers.registry import WORKERS

WhichFn = Callable[[str], str | None]
RunnerFn = Callable[..., Any]


def probe(
    worker: str,
    model: str = "",
    *,
    which: WhichFn | None = None,
    runner: RunnerFn | None = None,
    timeout: int = 30,
    project_root: Path | None = None,
) -> tuple[bool, str]:
    """Check Pi SDK runtime readiness without opening a billed model turn."""
    del model, runner
    name = (worker or "").strip().lower()
    if name not in WORKERS:
        return False, f"不支持的 Agent：{worker}"
    ok, message = inspect(name, which=which, project_root=project_root)
    if not ok:
        return ok, message
    return check(
        name,
        which=which,
        timeout=timeout,
        project_root=project_root,
    )
