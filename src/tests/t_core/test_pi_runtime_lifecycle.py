"""pi-runtime lifetime: no runtime or MCP child may outlive its host (ISSUES #22/#23)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from backend.core.agents.providers.registry import ProviderDispatcher
from backend.core.agents.uv_env import resolve_uv_cache_dir
from backend.core.workflow import main as workflow_main
from backend.pi_client.env import runtime_env
from backend.pi_client.process import PiRuntimeProcess

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _gone(pid: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


@pytest.fixture
def mock_runtime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PI_RUNTIME_MOCK", "1")
    runtime = PiRuntimeProcess(PROJECT_ROOT)
    yield runtime
    runtime.shutdown(grace=2)


@pytest.mark.skipif(os.name == "nt", reason="POSIX process checks")
def test_runtime_exits_on_stdin_close(mock_runtime: PiRuntimeProcess) -> None:
    info = mock_runtime.request("runtime.info", timeout=30)
    assert info["mode"] == "mock"
    proc = mock_runtime._proc
    assert proc is not None
    proc.stdin.close()  # what happens when the host process dies
    assert proc.wait(timeout=10) == 0  # exited by itself, not killed


@pytest.mark.skipif(os.name == "nt", reason="POSIX process checks")
def test_orchestrator_shutdown_kills_runtime(mock_runtime: PiRuntimeProcess) -> None:
    mock_runtime.request("protocol.version", timeout=30)
    pid = mock_runtime.pid
    assert pid
    mock_runtime.shutdown()
    assert _gone(pid)
    assert mock_runtime.pid is None
    # restartable after shutdown (the backend keeps serving model/auth requests)
    assert mock_runtime.request("protocol.version", timeout=30) == {"version": 1}
    assert mock_runtime.pid and mock_runtime.pid != pid


def test_workflow_main_closes_session_client() -> None:
    calls: list[str] = []

    class Client:
        def close(self) -> None:
            calls.append("close")

    workflow_main._close_session_client(Client())
    workflow_main._close_session_client(object())  # no close(): ignored
    assert calls == ["close"]


def test_dispatcher_close_closes_providers() -> None:
    calls: list[str] = []

    class Provider:
        def close(self) -> None:
            calls.append("close")

    dispatcher = ProviderDispatcher()
    dispatcher._providers["pi"] = Provider()  # type: ignore[assignment]
    dispatcher.close()
    assert calls == ["close"]
    assert dispatcher._providers == {}


def test_runtime_env_is_whitelisted(tmp_path: Path) -> None:
    base = {
        "PATH": "/usr/bin",
        "HOME": "/home/u",
        "LANG": "zh_CN.UTF-8",
        "LC_ALL": "C",
        "PYTHONPATH": "src:.",
        "LCA_FOO": "1",
        "PI_MODEL": "deepseek/deepseek-chat",
        "OPENLCA_IPC_PORT": "8080",
        "DEEPSEEK_API_KEY": "k",
        "MY_PROVIDER_API_KEY": "k2",
        "HTTPS_PROXY": "http://proxy:1",
        "UV_CACHE_DIR": "/tmp/cursor-sandbox-cache/abc/uv",
        "CURSOR_SANDBOX": "1",
        "AMBERHOME": "/opt/amber",
        "DBUS_SESSION_BUS_ADDRESS": "x",
    }
    env = runtime_env(tmp_path, base)
    for key in (
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "PYTHONPATH",
        "LCA_FOO",
        "PI_MODEL",
        "OPENLCA_IPC_PORT",
        "DEEPSEEK_API_KEY",
        "MY_PROVIDER_API_KEY",
        "HTTPS_PROXY",
    ):
        assert env[key] == base[key], key
    for key in ("CURSOR_SANDBOX", "AMBERHOME", "DBUS_SESSION_BUS_ADDRESS"):
        assert key not in env
    assert env["UV_CACHE_DIR"] == str((tmp_path / ".uv-cache").resolve())


def test_uv_cache_dir_stays_inside_project(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    assert resolve_uv_cache_dir(root, env={}) == root / ".uv-cache"
    assert resolve_uv_cache_dir(root, env={"UV_CACHE_DIR": "cache/uv"}) == root / "cache/uv"
    assert (
        resolve_uv_cache_dir(root, env={"UV_CACHE_DIR": str(root / "x")}) == root / "x"
    )
    assert (
        resolve_uv_cache_dir(root, env={"UV_CACHE_DIR": "/tmp/cursor-sandbox-cache/u"})
        == root / ".uv-cache"
    )
