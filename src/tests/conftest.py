"""Test isolation: temp workspace, never the real openLCA ports, never the real workspace plan."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "src" / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "src" / "frontend"
WEB_ROOT = FRONTEND_ROOT / "web"
WORKFLOWS = PROJECT_ROOT / "harness" / "workflows"

# ---------------------------------------------------------------------------
# 测试隔离：绝不碰真实 openLCA（8080 / .env 配置端口）和真实 workspace。
# ---------------------------------------------------------------------------

_LIVE_OPENLCA_PORT = 8080
_UNUSED_TEST_OPENLCA_PORT = "1"  # 保留端口，连接必然被拒，不会命中任何服务


def _configured_live_ports() -> set[int]:
    ports = {_LIVE_OPENLCA_PORT}
    for source in (os.environ.get("OPENLCA_IPC_PORT", ""),):
        if source.strip().isdigit():
            ports.add(int(source.strip()))
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "OPENLCA_IPC_PORT" and value.strip().strip("'\"").isdigit():
                ports.add(int(value.strip().strip("'\"")))
    return ports


_FORBIDDEN_PORTS = _configured_live_ports()
os.environ["LCA_TEST_FORBIDDEN_OPENLCA_PORTS"] = ",".join(str(p) for p in sorted(_FORBIDDEN_PORTS))
os.environ["OPENLCA_IPC_PORT"] = _UNUSED_TEST_OPENLCA_PORT

_real_socket_connect = socket.socket.connect
_real_create_connection = socket.create_connection


def _blocked(address: object) -> bool:
    return (
        isinstance(address, tuple)
        and len(address) >= 2
        and isinstance(address[1], int)
        and address[1] in _FORBIDDEN_PORTS
    )


def _guarded_connect(self: socket.socket, address: object) -> None:  # type: ignore[override]
    if _blocked(address):
        raise RuntimeError(f"tests must not connect to real openLCA port {address}")
    return _real_socket_connect(self, address)


def _guarded_create_connection(address: object, *args: object, **kwargs: object):
    if _blocked(address):
        raise RuntimeError(f"tests must not connect to real openLCA port {address}")
    return _real_create_connection(address, *args, **kwargs)  # type: ignore[arg-type]


socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
socket.create_connection = _guarded_create_connection  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _isolate_live_resources(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """每个测试默认用临时 workspace，并指向不存在服务的 openLCA 端口。"""
    tmp_ws = tmp_path_factory.mktemp("lca-workspace")
    monkeypatch.setenv("LCA_WORKSPACE", str(tmp_ws))
    monkeypatch.setenv("OPENLCA_IPC_PORT", _UNUSED_TEST_OPENLCA_PORT)
    monkeypatch.setenv(
        "LCA_TEST_FORBIDDEN_OPENLCA_PORTS",
        ",".join(str(p) for p in sorted(_FORBIDDEN_PORTS)),
    )
