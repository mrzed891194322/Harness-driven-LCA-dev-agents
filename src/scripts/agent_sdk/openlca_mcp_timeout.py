"""Worker MCP tool timeout aligned with control_openlca IPC session budget."""

from __future__ import annotations


def mcp_tool_timeout_sec() -> int:
    from harness.tools.control_openlca.utils.connection import (
        mcp_tool_timeout_sec as _budget,
    )

    return _budget()
