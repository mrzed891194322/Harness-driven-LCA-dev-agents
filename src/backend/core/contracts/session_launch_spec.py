"""Cross-language session launch contract (schema_version=2). Single source of truth.

``src/scripts/export_contracts.py`` exports ``session_launch_spec.schema.json`` and
``pi-runtime/src/spec.generated.ts`` from these classes; a test keeps the committed files in sync.
Only fields v5 uses are kept (WORKFLOW_DESIGN §7).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypedDict

SCHEMA_VERSION = 2


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
        out: dict[str, Any] = {"profile_id": self.profile_id, "provider": self.provider, "model_id": self.model_id}
        for key in ("display_name", "api_type", "base_url"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        if self.parameters:
            out["parameters"] = dict(self.parameters)
        return out


@dataclass
class SystemSection:
    id: str
    content: str
    source_hash: str


@dataclass
class KnowledgeBinding:
    id: str
    root_path: str
    content_hash: str
    summary: str = ""


@dataclass
class PermissionPolicy:
    allowed_tools: list[str]
    allowed_read_globs: list[str]
    allowed_write_globs: list[str]
    deny_shell: bool = True
    # Official deliverable paths only the submit/spec MCP may write (beats allowed_write_globs).
    denied_write_globs: list[str] = field(default_factory=list)


class ResourceBindings(TypedDict):
    project_root: str
    credentials_dir: str


class SessionStorage(TypedDict):
    agent_dir: str
    session_file: str


class McpBinding(TypedDict, total=False):
    command: str
    args: list[str]
    env: dict[str, str]
    timeout_ms: int
    exposure: Literal["direct", "deferred", "codemode", "hidden"]


@dataclass
class SessionLaunchSpec:
    run_id: str
    node: str
    rev: int
    agent: str
    attempt: int
    session_key: str
    model_profile: ModelProfile
    system_sections: list[SystemSection]
    turn_context: dict[str, Any]
    knowledge_bindings: list[KnowledgeBinding]
    resource_bindings: ResourceBindings
    mcp_bindings: dict[str, McpBinding]
    permission_policy: PermissionPolicy
    session_storage: SessionStorage
    schema_version: Literal[2] = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["model_profile"] = self.model_profile.to_dict()
        for k in out["knowledge_bindings"]:
            if not k.get("summary"):
                k.pop("summary", None)
        return {"schema_version": out.pop("schema_version"), **out}
