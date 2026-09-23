"""Resolved per-assignment task configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from core.workflow.spec.models import McpCallSpec, StageSpec


@dataclass(frozen=True)
class KnowledgeBinding:
    knowledge_id: str
    kind: str
    path: str
    provider: str

    def to_dict(self) -> dict[str, str]:
        return {
            "knowledge_id": self.knowledge_id,
            "kind": self.kind,
            "path": self.path,
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KnowledgeBinding:
        return cls(
            knowledge_id=str(payload["knowledge_id"]),
            kind=str(payload["kind"]),
            path=str(payload["path"]),
            provider=str(payload.get("provider") or "local_files"),
        )


@dataclass
class TaskBundle:
    workflow_id: str
    stage_id: str
    assignment_id: str
    role: str
    max_attempts: int
    stage_spec: StageSpec
    rule_ids: list[str] = field(default_factory=list)
    tool_ids: list[str] = field(default_factory=list)
    knowledge_ids: list[str] = field(default_factory=list)
    knowledge_sources: list[KnowledgeBinding] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    acceptance_checks: list[McpCallSpec] = field(default_factory=list)
    on_reviewer_passed: list[McpCallSpec] = field(default_factory=list)
    context: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("stage_spec", None)
        payload["stage_spec_path"] = self.stage_spec.source_path
        payload["acceptance_checks"] = [
            item.to_dict() for item in self.acceptance_checks
        ]
        payload["on_reviewer_passed"] = [
            item.to_dict() for item in self.on_reviewer_passed
        ]
        payload["knowledge_sources"] = [
            item.to_dict() for item in self.knowledge_sources
        ]
        return payload
