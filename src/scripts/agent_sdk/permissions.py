"""Headless worker permission policy.

Providers map these constants onto native CLI flags. Tool names and sandbox
primitives differ per CLI; do not assume one argv works for every worker.
Write confinement to LCA ``workspace/`` remains a prompt rule, not an OS lock.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CLAUDE_PERMISSION_MODE = "dontAsk"
CLAUDE_BUILTIN_TOOLS: tuple[str, ...] = (
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
)

PI_BUILTIN_TOOLS: tuple[str, ...] = (
    "read",
    "bash",
    "edit",
    "write",
    "grep",
    "find",
    "ls",
)

CODEX_SANDBOX = "workspace-write"
OPENCODE_BUILTIN_PERMISSIONS: tuple[str, ...] = (
    "read",
    "edit",
    "glob",
    "grep",
    "bash",
)


def claude_allowed_tools(
    mcp_servers: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    extras = tuple(f"mcp__{name}" for name in (mcp_servers or {}))
    return CLAUDE_BUILTIN_TOOLS + extras


def claude_allowed_tools_flag(
    mcp_servers: Mapping[str, Any] | None = None,
) -> str:
    return ",".join(claude_allowed_tools(mcp_servers))


def pi_tools(
    mcp_servers: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    # pi-mcp-adapter exposes proxy tools mcp / mcpScript, not mcp__<server>.
    extras = ("mcp", "mcpScript") if mcp_servers else ()
    return PI_BUILTIN_TOOLS + extras


def pi_tools_flag(
    mcp_servers: Mapping[str, Any] | None = None,
) -> str:
    return ",".join(pi_tools(mcp_servers))


def opencode_permission_config(
    mcp_servers: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Deny-by-default OpenCode permission map for one worker turn."""
    permission = {"*": "deny"}
    for name in OPENCODE_BUILTIN_PERMISSIONS:
        permission[name] = "allow"
    for server in mcp_servers or {}:
        key = str(server).strip()
        if key:
            permission[f"{key}_*"] = "allow"
    return permission
