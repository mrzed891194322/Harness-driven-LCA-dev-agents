"""测试不得连接真实 openLCA（8080）或写真实 workspace。"""

from __future__ import annotations

import os
import socket

import pytest

from harness.tools.shared.control_openlca import cleanup, connection


def test_create_ipc_client_refuses_8080() -> None:
    with pytest.raises(connection.LiveOpenLCAForbiddenError):
        connection.create_ipc_client("127.0.0.1", 8080)


def test_cleanup_connect_ipc_refuses_8080() -> None:
    with pytest.raises(connection.LiveOpenLCAForbiddenError):
        cleanup.connect_ipc("127.0.0.1", 8080)


def test_probe_and_connect_refuse_8080() -> None:
    with pytest.raises(connection.LiveOpenLCAForbiddenError):
        connection.probe_ipc("127.0.0.1", 8080)


def test_raw_socket_to_8080_blocked() -> None:
    with pytest.raises(RuntimeError, match="real openLCA"):
        socket.create_connection(("127.0.0.1", 8080), timeout=0.1)


def test_env_points_away_from_live() -> None:
    assert os.environ["OPENLCA_IPC_PORT"] != "8080"
    assert "8080" in os.environ["LCA_TEST_FORBIDDEN_OPENLCA_PORTS"].split(",")


def test_lca_artifacts_context_uses_tmp_workspace() -> None:
    from harness.tools.shared.lca_artifacts.store import PROJECT_ROOT, Context

    ctx = Context.from_env()
    assert ctx.workspace != (PROJECT_ROOT / "workspace").resolve()


def test_lca_artifacts_context_refuses_real_workspace_fallback(monkeypatch) -> None:
    from harness.tools.shared.lca_artifacts.store import Context, HostContextError

    monkeypatch.delenv("LCA_WORKSPACE", raising=False)
    with pytest.raises(HostContextError):
        Context.from_env()
