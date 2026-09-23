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
class McpCallSpec:
    """Declarative stdio MCP invocation (host or lifecycle)."""

    id: str
    tool: str
    call: str
    arguments: dict[str, Any] = field(default_factory=dict)
    state_call: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "tool": self.tool,
            "call": self.call,
            "arguments": dict(self.arguments),
        }
        if self.state_call:
            payload["state_call"] = self.state_call
        return payload


@dataclass
class StageSpec:
    """Parsed stage ``spec.yaml`` — machine contract only."""

    version: int
    spec_id: str
    source_path: str
    inputs: list[PathContract] = field(default_factory=list)
    outputs: list[PathContract] = field(default_factory=list)
    acceptance_checks: list[McpCallSpec] = field(default_factory=list)
    on_reviewer_passed: list[McpCallSpec] = field(default_factory=list)
    handoff_schema: str | None = None
    handoff_checks: list[McpCallSpec] = field(default_factory=list)

    def output_paths(self) -> list[str]:
        return [item.path for item in self.outputs if item.required]
