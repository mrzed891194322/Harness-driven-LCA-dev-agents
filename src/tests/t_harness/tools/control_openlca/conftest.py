from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _control_openlca_mcp_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline tests invoke v2 tools directly; emulate MCP server process env."""
    monkeypatch.setenv("LCA_CONTROL_OPENLCA_MCP", "1")
