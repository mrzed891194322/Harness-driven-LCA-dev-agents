"""Convert workflow tool registry entries to session mcp_servers dicts."""

from __future__ import annotations

import sys
from typing import Any


def tool_entry_to_mcp(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "transport": spec.get("transport") or "stdio",
    }
    if spec.get("command"):
        payload["command"] = spec["command"]
    if spec.get("args"):
        payload["args"] = list(spec["args"])
    if spec.get("url"):
        payload["url"] = spec["url"]
    if spec.get("env"):
        payload["env"] = dict(spec["env"])
    if spec.get("headers"):
        payload["headers"] = dict(spec["headers"])
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
    rewrite_uv: bool = True,
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
