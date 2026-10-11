from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _control_openlca_mcp_stdio(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Offline tests invoke v2 tools directly; emulate MCP server process env."""
    monkeypatch.setenv("LCA_CONTROL_OPENLCA_MCP", "1")
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "ipc-locks"))
