"""Convert workflow tool registry entries to session mcp_servers dicts."""

from __future__ import annotations

import sys
from typing import Any

DEFAULT_TOOL_TIMEOUT_SEC = 60


def validate_stdio_server(name: str, spec: dict[str, Any]) -> None:
    """Reject unsupported or malformed launch configs before starting a worker."""
    transport = spec.get("transport", "stdio")
    if transport != "stdio":
        raise ValueError(
            f"MCP {name}: unsupported transport {transport!r}; only stdio is supported"
        )
    if not isinstance(spec.get("command"), str) or not spec["command"].strip():
        raise ValueError(f"MCP {name}: command must be a nonempty string")
    args = spec.get("args", [])
    if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
        raise ValueError(f"MCP {name}: args must be a list of strings")
    env = spec.get("env", {})
    if not isinstance(env, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in env.items()
    ):
        raise ValueError(f"MCP {name}: env must map strings to strings")
    if "url" in spec or "headers" in spec:
        raise ValueError(f"MCP {name}: url/headers are not supported for stdio")
    timeout = spec.get("tool_timeout_sec", DEFAULT_TOOL_TIMEOUT_SEC)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise ValueError(f"MCP {name}: tool_timeout_sec must be a positive integer")


def tool_entry_to_mcp(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    validate_stdio_server(name, spec)
    payload: dict[str, Any] = {
        "transport": spec.get("transport") or "stdio",
        "tool_timeout_sec": spec.get("tool_timeout_sec", DEFAULT_TOOL_TIMEOUT_SEC),
    }
    if spec.get("command"):
        payload["command"] = spec["command"]
    if spec.get("args"):
        payload["args"] = list(spec["args"])
    if spec.get("env"):
        payload["env"] = dict(spec["env"])
    payload["name"] = name
    return payload


def rewrite_uv_run_python(server: dict[str, Any]) -> dict[str, Any]:
    """Replace ``uv run python <script> ...`` with the current interpreter.

    YAML may still declare ``command: uv`` as intent; runtime MCP children reuse
    the orchestrator's already-resolved ``.venv`` via ``sys.executable``.
    """
    command = str(server.get("command") or "")
    args = [str(item) for item in list(server.get("args") or [])]
    if command != "uv" or len(args) < 3:
        return server
    if args[0] != "run" or args[1] != "python":
        return server
    rewritten = dict(server)
    rewritten["command"] = sys.executable
    rewritten["args"] = args[2:]
    return rewritten


def mcp_servers_for_tools(
    tool_ids: list[str],
    registry_tools: dict[str, dict[str, Any]],
    *,
    rewrite_uv: bool = False,
) -> dict[str, dict[str, Any]]:
    servers: dict[str, dict[str, Any]] = {}
    for tool_id in tool_ids:
        spec = registry_tools.get(tool_id)
        if spec is None:
            raise KeyError(f"unknown tool id: {tool_id}")
        entry = tool_entry_to_mcp(tool_id, spec)
        if rewrite_uv:
            entry = rewrite_uv_run_python(entry)
        servers[tool_id] = entry
    return servers
