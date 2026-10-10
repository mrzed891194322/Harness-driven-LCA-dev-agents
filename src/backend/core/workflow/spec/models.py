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


@dataclass(frozen=True)
class SubmitCheck:
    """One acceptance check run by spec_mcp ``submit`` (acceptance.yaml)."""

    check: str
    params: dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"check": self.check, "params": dict(self.params), "summary": self.summary}


@dataclass(frozen=True)
class Deliverable:
    """A stage deliverable. ``writer=spec_mcp`` paths are writable only by spec_mcp."""

    name: str
    path: str
    kind: str = "file"
    format: str | None = None
    required: bool = True
    writer: str = "spec_mcp"  # spec_mcp | agent
    schema: str | None = None  # project-relative effective path (default or user)
    example: str | None = None  # project-relative effective path

    def contract(self) -> PathContract:
        return PathContract(
            path=self.path,
            required=self.required,
            kind=self.kind,
            format=self.format,
            schema=self.schema,
        )


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
    deliverables: list[Deliverable] = field(default_factory=list)
    submit_checks: dict[str, list[SubmitCheck]] = field(default_factory=dict)
    # role -> permission rule ids (harness/specs/shared/permissions/<id>.yaml)
    role_permissions: dict[str, list[str]] = field(default_factory=dict)
    # harness-relative file -> {"source": "default"|"user", "sha256": ...}
    sources: dict[str, dict[str, str]] = field(default_factory=dict)

    def output_paths(self) -> list[str]:
        return [item.path for item in self.outputs if item.required]
