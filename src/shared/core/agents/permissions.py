"""Headless Pi worker permission policy.

Write confinement to the project ``workspace/`` remains a prompt rule, not an OS lock.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PI_BUILTIN_TOOLS: tuple[str, ...] = (
    "read",
    "bash",
    "edit",
    "write",
    "grep",
    "find",
    "ls",
)


def pi_tools(
    mcp_servers: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    # Pi SDK registers MCP tools as mcp__<server>__<tool> and the allowlist is
    # matched by name (``*`` patterns allowed), so allow each bound server's tools.
    extras = tuple(f"mcp__{name}__*" for name in (mcp_servers or {}))
    return PI_BUILTIN_TOOLS + extras


def pi_tools_flag(
    mcp_servers: Mapping[str, Any] | None = None,
) -> str:
    return ",".join(pi_tools(mcp_servers))
