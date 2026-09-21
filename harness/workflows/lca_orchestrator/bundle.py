"""Resolved per-assignment task configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CheckRef:
    profile: str

    def to_dict(self) -> dict[str, str]:
        return {"profile": self.profile}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CheckRef:
        return cls(profile=str(payload["profile"]))


@dataclass(frozen=True)
class KnowledgeBinding:
    knowledge_id: str
    kind: str
    path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "knowledge_id": self.knowledge_id,
            "kind": self.kind,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KnowledgeBinding:
        return cls(
            knowledge_id=str(payload["knowledge_id"]),
            kind=str(payload["kind"]),
            path=str(payload["path"]),
        )


@dataclass
class TaskBundle:
    workflow_id: str
    stage_id: str
    assignment_id: str
    role: str
    max_attempts: int
    runtime_spec: str
    spec_paths: list[str] = field(default_factory=list)
    rule_ids: list[str] = field(default_factory=list)
    tool_ids: list[str] = field(default_factory=list)
    knowledge_ids: list[str] = field(default_factory=list)
    knowledge_sources: list[KnowledgeBinding] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    checks: list[CheckRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [item.to_dict() for item in self.checks]
        payload["knowledge_sources"] = [
            item.to_dict() for item in self.knowledge_sources
        ]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TaskBundle:
        return cls(
            workflow_id=str(payload["workflow_id"]),
            stage_id=str(payload["stage_id"]),
            assignment_id=str(payload["assignment_id"]),
            role=str(payload["role"]),
            max_attempts=int(payload["max_attempts"]),
            runtime_spec=str(payload["runtime_spec"]),
            spec_paths=[str(item) for item in payload.get("spec_paths") or []],
            rule_ids=[str(item) for item in payload.get("rule_ids") or []],
            tool_ids=[str(item) for item in payload.get("tool_ids") or []],
            knowledge_ids=[str(item) for item in payload.get("knowledge_ids") or []],
            knowledge_sources=[
                KnowledgeBinding.from_dict(item)
                for item in payload.get("knowledge_sources") or []
            ],
            expected_outputs=[
                str(item) for item in payload.get("expected_outputs") or []
            ],
            checks=[CheckRef.from_dict(item) for item in payload.get("checks") or []],
        )
