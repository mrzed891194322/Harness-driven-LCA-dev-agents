"""Workflow YAML models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.agents.mcp import DEFAULT_TOOL_TIMEOUT_SEC
from core.runtime.tool_runtime import ToolRuntimeSpec

if TYPE_CHECKING:
    from .bundle import TaskBundle


@dataclass
class McpToolSpec:
    """Agent-facing stdio MCP tool registration."""

    tool_id: str
    transport: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    runtime: ToolRuntimeSpec | None = None
    tool_timeout_sec: int = DEFAULT_TOOL_TIMEOUT_SEC

    def to_mcp_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "transport": self.transport,
            "tool_timeout_sec": self.tool_timeout_sec,
        }
        if self.command:
            payload["command"] = self.command
        if self.args:
            payload["args"] = list(self.args)
        if self.env:
            payload["env"] = dict(self.env)
        return payload


@dataclass
class HostActionSpec:
    """Core-facing Host Action registration (JSON stdin/stdout, not MCP)."""

    action_id: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout_sec: int = DEFAULT_TOOL_TIMEOUT_SEC

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "command": self.command,
            "args": list(self.args),
            "env": dict(self.env),
            "timeout_sec": self.timeout_sec,
        }


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
    tools_decl: Any | None = None  # {"mcp": list|patch} or None
    rules_decl: Any | None = None
    knowledge_decl: Any | None = None


@dataclass
class Stage:
    stage_id: str
    spec: str
    max_attempts: int
    steps: list[str]
    knowledge_decl: Any | None = None
    rules_decl: Any | None = None
    tools_decl: Any | None = None  # {"mcp": list|patch} or None
    context: dict[str, object] = field(default_factory=dict)


@dataclass
class Workflow:
    workflow_id: str
    max_attempts: int
    rules: dict[str, str]
    mcp_tools: dict[str, McpToolSpec]
    host_actions: dict[str, HostActionSpec]
    knowledge: dict[str, KnowledgeSource]
    default_rules: list[str]
    default_knowledge: list[str]
    stages: list[Stage]
    assignments: dict[str, Assignment]
    source_path: Path
    bundles: dict[str, TaskBundle] = field(default_factory=dict)

    def stage_by_id(self, stage_id: str) -> Stage:
        for stage in self.stages:
            if stage.stage_id == stage_id:
                return stage
        raise KeyError(stage_id)

    def assignment_for(self, stage: Stage, step_index: int) -> Assignment:
        assignment_id = stage.steps[step_index]
        return self.assignments[assignment_id]
