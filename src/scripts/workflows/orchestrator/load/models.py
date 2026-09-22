"""Workflow YAML models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scripts.workflows.runtime.tool_runtime import ToolRuntimeSpec

from .bundle import CheckRef

if TYPE_CHECKING:
    from .bundle import TaskBundle


@dataclass
class ToolSpec:
    tool_id: str
    transport: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    runtime: ToolRuntimeSpec | None = None

    def to_mcp_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"transport": self.transport}
        if self.command:
            payload["command"] = self.command
        if self.args:
            payload["args"] = list(self.args)
        if self.url:
            payload["url"] = self.url
        if self.env:
            payload["env"] = dict(self.env)
        if self.headers:
            payload["headers"] = dict(self.headers)
        return payload


@dataclass
class KnowledgeSource:
    knowledge_id: str
    kind: str
    path: str
    provider: str = "local_files"


@dataclass
class Assignment:
    assignment_id: str
    role: str
    task_spec: str
    tools_decl: Any | None = None
    rules_decl: Any | None = None
    knowledge_decl: Any | None = None


@dataclass
class Stage:
    stage_id: str
    spec: str
    max_attempts: int
    steps: list[str]
    spec_additions: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    checks: list[CheckRef] = field(default_factory=list)
    knowledge_decl: Any | None = None
    rules_decl: Any | None = None
    tools_decl: Any | None = None
    reviewer_passed_hooks_decl: Any | None = None
    context: dict[str, object] = field(default_factory=dict)


@dataclass
class Workflow:
    workflow_id: str
    runtime_spec: str
    max_attempts: int
    rules: dict[str, str]
    tools: dict[str, ToolSpec]
    knowledge: dict[str, KnowledgeSource]
    default_rules: list[str]
    default_knowledge: list[str]
    stages: list[Stage]
    assignments: dict[str, Assignment]
    source_path: Path
    reviewer_passed_hooks: list[str] = field(default_factory=list)
    bundles: dict[str, TaskBundle] = field(default_factory=dict)
    capability_ids: list[str] = field(default_factory=list)

    def stage_by_id(self, stage_id: str) -> Stage:
        for stage in self.stages:
            if stage.stage_id == stage_id:
                return stage
        raise KeyError(stage_id)

    def assignment_for(self, stage: Stage, step_index: int) -> Assignment:
        assignment_id = stage.steps[step_index]
        return self.assignments[assignment_id]
