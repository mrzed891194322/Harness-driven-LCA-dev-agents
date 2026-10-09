"""Render MCP snippets for Pi SDK runtime (tests / diagnostics)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.agents.providers.store import write_stdio_mcp_snippet


def write_pi_mcp(path: Path, mcp_servers: dict[str, dict[str, Any]]) -> None:
    snippet = write_stdio_mcp_snippet(mcp_servers)
    servers: dict[str, Any] = {}
    for name, spec in snippet.items():
        if not spec.get("command"):
            continue
        entry: dict[str, Any] = {
            "command": spec["command"],
            "args": list(spec.get("args") or []),
        }
        if spec.get("env"):
            entry["env"] = dict(spec["env"])
        entry["timeout"] = int(spec.get("tool_timeout_sec", 60)) * 1000
        servers[name] = entry
    if servers:
        path.write_text(
            json.dumps({"mcpServers": servers}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    elif path.exists():
        path.unlink()
