"""Stage machine-readable contract models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PathContract:
    path: str
    required: bool = True
    kind: str = "file"  # file | directory
    format: str | None = None  # json | yaml | text | None
    schema: str | None = None  # repo-relative JSON Schema path


@dataclass(frozen=True)
class HostActionRef:
    """Reference to a workflow-registered Host Action (logical id)."""

    id: str
    action: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "arguments": dict(self.arguments),
        }


@dataclass
class StageSpec:
    """Parsed stage ``spec.yaml`` — machine contract only."""

    version: int
    spec_id: str
    source_path: str
    inputs: list[PathContract] = field(default_factory=list)
    outputs: list[PathContract] = field(default_factory=list)
    acceptance_checks: list[HostActionRef] = field(default_factory=list)
    on_reviewer_passed: list[HostActionRef] = field(default_factory=list)
    handoff_schema: str | None = None
    handoff_checks: list[HostActionRef] = field(default_factory=list)

    def output_paths(self) -> list[str]:
        return [item.path for item in self.outputs if item.required]
