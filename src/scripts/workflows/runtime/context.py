"""Generic run context for harness capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RunContext:
    project_root: Path
    workspace_root: Path
    run_id: str
    stage_id: str
    assignment_id: str
    attempt: int
    role: str
    metadata: dict[str, object] = field(default_factory=dict)
