"""Versioned cross-language session launch contract (schema_version=1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1


@dataclass
class ModelProfile:
    profile_id: str
    provider: str
    model_id: str
    display_name: str = ""
    api_type: str = ""
    base_url: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "provider": self.provider,
            "model_id": self.model_id,
        }
        if self.display_name:
            payload["display_name"] = self.display_name
        if self.api_type:
            payload["api_type"] = self.api_type
        if self.base_url:
            payload["base_url"] = self.base_url
        if self.parameters:
            payload["parameters"] = dict(self.parameters)
        return payload


@dataclass
class SystemSection:
    id: str
    content: str
    source_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "content": self.content, "source_hash": self.source_hash}


@dataclass
class KnowledgeBinding:
    id: str
    root_path: str
    content_hash: str
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "root_path": self.root_path,
            "content_hash": self.content_hash,
        }
        if self.summary:
            out["summary"] = self.summary
        return out


@dataclass
class PermissionPolicy:
    allowed_tools: list[str]
    allowed_read_globs: list[str]
    allowed_write_globs: list[str]
    deny_shell: bool = True
    # Official deliverable paths only spec_mcp may write (beats allowed_write_globs).
    denied_write_globs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_tools": list(self.allowed_tools),
            "allowed_read_globs": list(self.allowed_read_globs),
            "allowed_write_globs": list(self.allowed_write_globs),
            "deny_shell": self.deny_shell,
            "denied_write_globs": list(self.denied_write_globs),
        }


@dataclass
class SessionLaunchSpec:
    run_id: str
    stage_id: str
    assignment_id: str
    role: str
    attempt: int
    session_key: str
    execution_id: str
    bundle_hash: str
    input_snapshot_hash: str
    model_profile: ModelProfile
    system_sections: list[SystemSection]
    turn_context: dict[str, Any]
    knowledge_bindings: list[KnowledgeBinding]
    resource_bindings: dict[str, str]
    mcp_bindings: dict[str, dict[str, Any]]
    permission_policy: PermissionPolicy
    session_storage: dict[str, str]
    handoff_binding: dict[str, str] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    # Host-only diagnostics for the injection manifest; never sent to pi-runtime.
    prompt_segments: list[dict[str, Any]] = field(default_factory=list, repr=False, compare=False)
    spec_view: dict[str, Any] | None = field(default=None, repr=False, compare=False)
    spec_view_hash: str = field(default="", repr=False, compare=False)
    spec_sources: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "stage_id": self.stage_id,
            "assignment_id": self.assignment_id,
            "role": self.role,
            "attempt": self.attempt,
            "session_key": self.session_key,
            "execution_id": self.execution_id,
            "bundle_hash": self.bundle_hash,
            "input_snapshot_hash": self.input_snapshot_hash,
            "model_profile": self.model_profile.to_dict(),
            "system_sections": [s.to_dict() for s in self.system_sections],
            "turn_context": dict(self.turn_context),
            "knowledge_bindings": [k.to_dict() for k in self.knowledge_bindings],
            "resource_bindings": dict(self.resource_bindings),
            "mcp_bindings": dict(self.mcp_bindings),
            "permission_policy": self.permission_policy.to_dict(),
            "session_storage": dict(self.session_storage),
        }
        if self.handoff_binding:
            payload["handoff_binding"] = dict(self.handoff_binding)
        return payload
