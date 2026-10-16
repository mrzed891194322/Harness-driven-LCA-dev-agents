"""Discover harness components by directory convention (PR2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.core.agents.mcp import DEFAULT_TOOL_TIMEOUT_SEC, validate_stdio_server
from backend.core.runtime import harness_fs
from backend.core.runtime.identifiers import require_component_id, require_relative_path
from backend.core.runtime.tool_runtime import ToolRuntimeSpec
from backend.core.workflow.config.models import HostActionSpec, KnowledgeSource, McpToolSpec

PROMPTS_ROOT = "prompts"
PERMISSIONS_ROOT = "permissions"
MCP_ROOT = "tools/mcp"
HOST_ACTION_SCRIPT = "harness/tools/host_action/lca_artifacts/main.py"
HOST_ACTION_CLI_MAP: dict[str, str] = {
    "check/inventory": "inventory-check",
    "check/mapping": "mapping-check",
    "check/report": "report-check",
    "check/record-acceptance": "record-acceptance",
}

_MCP_MANIFEST_KEYS = frozenset(
    {
        "transport",
        "command",
        "args",
        "env",
        "rules",
        "runtime",
        "tool_timeout_sec",
    }
)
_TOOL_RUNTIME_KEYS = frozenset(
    {
        "run_context_env",
        "context_file",
        "context_file_flag",
        "env_prefix",
        "use_host_python",
    }
)


def _parse_tool_runtime(spec: dict[str, Any], *, label: str) -> ToolRuntimeSpec | None:
    raw = spec.get("runtime")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{label}: runtime must be a mapping")
    unknown = set(raw) - _TOOL_RUNTIME_KEYS
    if unknown:
        raise ValueError(f"{label}: runtime unknown keys {sorted(unknown)}")
    return ToolRuntimeSpec(
        run_context_env=bool(raw.get("run_context_env", False)),
        context_file=bool(raw.get("context_file", False)),
        context_file_flag=str(raw.get("context_file_flag") or "--context-file"),
        env_prefix=str(raw["env_prefix"]) if raw.get("env_prefix") else None,
        use_host_python=bool(raw.get("use_host_python", False)),
    )


def _require_positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer, got {value!r}")
    return value


def _prompt_id_for_rel(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if len(parts) < 3 or parts[0] != PROMPTS_ROOT:
        raise ValueError(f"not a prompt rel: {rel}")
    subdir, filename = parts[1], parts[-1]
    stem = filename[: -len(".md")] if filename.endswith(".md") else filename
    if subdir == "project":
        return stem
    if subdir == "lca":
        return f"lca-{stem}"
    if subdir == "tools":
        return "tool-" + stem.replace("_", "-")
    if subdir == "stages":
        return f"stage/{stem}"
    raise ValueError(f"unknown prompt subdir {subdir!r}")


def discover_prompt_rules(project_root: Path) -> dict[str, str]:
    rules: dict[str, str] = {}
    base = project_root / "harness" / PROMPTS_ROOT
    if not base.is_dir():
        return rules
    for path in sorted(base.rglob("*.md")):
        if path.name == "README.md":
            continue
        rel = path.relative_to(project_root / "harness").as_posix()
        rid = require_component_id(_prompt_id_for_rel(rel), label="prompt rule id")
        rules[rid] = require_relative_path(f"harness/{rel}", label=f"prompt {rid}")
    return rules


def discover_permissions(project_root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in harness_fs.list_dir(project_root, PERMISSIONS_ROOT, (".yaml",)):
        name = Path(rel).name
        pid = require_component_id(name[: -len(".yaml")], label="permission id")
        out[pid] = require_relative_path(f"harness/{rel}", label=f"permission {pid}")
    return out


def _load_mcp_manifest(path: Path) -> McpToolSpec:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: mcp.yaml must be a mapping")
    tid = require_component_id(str(raw.get("id") or path.parent.name), label="mcp id")
    unknown = set(raw) - _MCP_MANIFEST_KEYS - {"id", "description", "tools"}
    if unknown:
        raise ValueError(f"{path}: unknown keys {sorted(unknown)}")
    spec = {k: raw[k] for k in raw if k not in ("id", "description", "tools")}
    validate_stdio_server(tid, spec)
    timeout = spec.get("tool_timeout_sec", DEFAULT_TOOL_TIMEOUT_SEC)
    timeout = _require_positive_int(timeout, label=f"{path}: tool_timeout_sec")
    rule_ids = [
        require_component_id(str(item), label="mcp rule id")
        for item in raw.get("rules") or []
    ]
    return McpToolSpec(
        tool_id=tid,
        transport=str(spec.get("transport") or "stdio"),
        command=spec.get("command"),
        args=[str(item) for item in spec.get("args") or []],
        env={str(k): str(v) for k, v in dict(spec.get("env") or {}).items()},
        rules=rule_ids,
        runtime=_parse_tool_runtime(spec, label=str(path)),
        tool_timeout_sec=timeout,
    )


def discover_mcp_tools(project_root: Path) -> dict[str, McpToolSpec]:
    tools: dict[str, McpToolSpec] = {}
    mcp_base = project_root / "harness" / MCP_ROOT
    if not mcp_base.is_dir():
        return tools
    for manifest in sorted(mcp_base.glob("*/mcp.yaml")):
        tool = _load_mcp_manifest(manifest)
        if tool.tool_id in tools:
            raise ValueError(f"duplicate mcp id {tool.tool_id!r}")
        tools[tool.tool_id] = tool
    return tools


def discover_host_actions(project_root: Path) -> dict[str, HostActionSpec]:
    if not (project_root / HOST_ACTION_SCRIPT).is_file():
        return {}
    actions: dict[str, HostActionSpec] = {}
    for aid, cli in HOST_ACTION_CLI_MAP.items():
        cid = require_component_id(aid, label="host_action id")
        actions[cid] = HostActionSpec(
            action_id=cid,
            command="uv",
            args=["run", "python", HOST_ACTION_SCRIPT, cli],
            env={},
            timeout_sec=60,
        )
    return actions


def discover_knowledge(project_root: Path) -> dict[str, KnowledgeSource]:
    del project_root
    return {
        "workspace_knowledge": KnowledgeSource(
            knowledge_id="workspace_knowledge",
            kind="local_dir",
            path="harness/knowledge/inputs/",
            provider="local_files",
        ),
        "workflow_plan": KnowledgeSource(
            knowledge_id="workflow_plan",
            kind="local_dir",
            path="harness/knowledge/plan/",
            provider="local_files",
        ),
    }


def discover_registry(project_root: Path) -> dict[str, Any]:
    return {
        "rules": discover_prompt_rules(project_root),
        "permissions": discover_permissions(project_root),
        "mcp": discover_mcp_tools(project_root),
        "host_action": discover_host_actions(project_root),
        "knowledge": discover_knowledge(project_root),
    }


def registry_catalog(project_root: Path) -> dict[str, Any]:
    """JSON view of the discovered components (for the GUI; YAML has no registry)."""
    from dataclasses import asdict

    found = discover_registry(project_root)
    return {
        "rules": dict(found["rules"]),
        "permissions": dict(found["permissions"]),
        "mcp": {
            tid: {
                "transport": spec.transport,
                "command": spec.command or "",
                "args": list(spec.args),
                "rules": list(spec.rules),
                "tool_timeout_sec": spec.tool_timeout_sec,
                "runtime": asdict(spec.runtime) if spec.runtime else {},
            }
            for tid, spec in found["mcp"].items()
        },
        "host_action": {
            aid: {
                "command": spec.command,
                "args": list(spec.args),
                "timeout_sec": spec.timeout_sec,
            }
            for aid, spec in found["host_action"].items()
        },
        "knowledge": {
            kid: {"kind": src.kind, "path": src.path, "provider": src.provider}
            for kid, src in found["knowledge"].items()
        },
    }
