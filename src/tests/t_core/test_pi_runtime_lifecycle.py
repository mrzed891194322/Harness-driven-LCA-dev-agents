"""pi-runtime lifetime: ONE runtime per project, shared by every client (ISSUES #22/#23).

The runtime is a service on a Unix socket (started by ``npm run dev``). Python
clients connect to it, never spawn one, and closing a client releases only that
client's sessions (and their MCP servers).
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.core.agents.inspect import check
from backend.core.agents.providers.registry import ProviderDispatcher
from backend.core.agents.uv_env import resolve_uv_cache_dir
from backend.core.workflow import main as workflow_main
from backend.pi_client.env import runtime_env
from backend.pi_client.process import (
    NOT_RUNNING,
    EndpointError,
    PiRuntimeClient,
    RuntimeNotRunning,
    runtime_endpoint,
    runtime_entry,
    socket_path,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
posix_only = pytest.mark.skipif(os.name == "nt", reason="Unix socket service")


def _gone(pid: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


def _wait(check_fn, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check_fn():
            return True
        time.sleep(0.1)
    return bool(check_fn())


class _Service:
    def __init__(self, sock: Path) -> None:
        self.sock = sock
        self.proc: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        env = {**os.environ, "PI_RUNTIME_MOCK": "1"}
        env.pop("PI_RUNTIME_PRIVATE", None)
        self.proc = subprocess.Popen(
            [*runtime_entry(PROJECT_ROOT), "--listen", str(self.sock)],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert _wait(self.sock.exists), "pi-runtime service did not listen"

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)


@pytest.fixture
def service() -> Iterator[_Service]:
    # Short directory: Unix socket paths are limited to ~104 bytes.
    with tempfile.TemporaryDirectory(prefix="pirt-") as tmp:
        svc = _Service(Path(tmp) / "rt.sock")
        svc.start()
        try:
            yield svc
        finally:
            svc.stop()


def _mock_spec(tmp: Path, key: str) -> dict:
    return {
        "schema_version": 1,
        "run_id": "",
        "stage_id": "t",
        "assignment_id": key,
        "role": "executor",
        "attempt": 1,
        "session_key": key,
        "execution_id": key,
        "bundle_hash": "h",
        "input_snapshot_hash": "h",
        "model_profile": {"profile_id": "fake", "provider": "fake-local", "model_id": "m"},
        "system_sections": [],
        "turn_context": {},
        "knowledge_bindings": [],
        "resource_bindings": {"project_root": str(tmp)},
        "mcp_bindings": {},
        "permission_policy": {
            "allowed_tools": [],
            "allowed_read_globs": [],
            "allowed_write_globs": [],
        },
        "session_storage": {
            "agent_dir": str(tmp / "agents" / key),
            "session_file": str(tmp / "sessions" / f"{key}.jsonl"),
        },
    }


@posix_only
def test_client_never_spawns_a_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PI_RUNTIME_PRIVATE", raising=False)
    client = PiRuntimeClient(PROJECT_ROOT, socket_file=tmp_path / "absent.sock")
    with pytest.raises(RuntimeNotRunning) as err:
        client.request("protocol.version", timeout=5)
    assert NOT_RUNNING in str(err.value)
    assert client.pid is None and not client.connected


def test_socket_path_default_and_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PI_RUNTIME_SOCKET", raising=False)
    assert socket_path(tmp_path) == tmp_path / ".local" / "run" / "pi-runtime.sock"
    monkeypatch.setenv("PI_RUNTIME_SOCKET", str(tmp_path / "x.sock"))
    assert socket_path(tmp_path) == tmp_path / "x.sock"


def test_runtime_endpoint_file_and_loopback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PI_RUNTIME_SOCKET", raising=False)
    recorded = tmp_path / ".local" / "run" / "pi-runtime.endpoint"
    recorded.parent.mkdir(parents=True)
    recorded.write_text("tcp://127.0.0.1:39123\n", encoding="utf-8")
    assert runtime_endpoint(tmp_path) == "tcp://127.0.0.1:39123"
    with pytest.raises(EndpointError):
        socket_path(tmp_path)
    recorded.write_text("tcp://10.0.0.8:80\n", encoding="utf-8")
    with pytest.raises(EndpointError, match="127.0.0.1"):
        runtime_endpoint(tmp_path)
    monkeypatch.setenv("PI_RUNTIME_SOCKET", str(tmp_path / "x.sock"))
    assert socket_path(tmp_path) == tmp_path / "x.sock"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def test_tcp_client_runtime_info_and_shutdown() -> None:
    port = _free_port()
    endpoint = f"tcp://127.0.0.1:{port}"
    env = {**os.environ, "PI_RUNTIME_MOCK": "1"}
    env.pop("PI_RUNTIME_PRIVATE", None)
    proc = subprocess.Popen(
        [*runtime_entry(PROJECT_ROOT), "--listen", endpoint],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = PiRuntimeClient(PROJECT_ROOT, endpoint=endpoint, private=False)
    try:
        assert _wait(lambda: _port_open(port), 20)
        info = client.request("runtime.info", timeout=10)
        assert info["socket"] == endpoint
        assert info["transport"] == "socket"
        assert info["mode"] == "mock"
        assert client.request("runtime.shutdown", timeout=10) == {
            "shutting_down": True
        }
        # wait() reaps the process. os.kill(pid, 0) still succeeds on a zombie.
        assert proc.wait(timeout=15) == 0
        assert not _port_open(port)
    finally:
        client.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


@posix_only
def test_backend_and_workflow_share_one_runtime(service: _Service, tmp_path: Path) -> None:
    backend = PiRuntimeClient(PROJECT_ROOT, socket_file=service.sock, private=False, label="backend")
    workflow = PiRuntimeClient(PROJECT_ROOT, socket_file=service.sock, private=False, label="workflow")
    try:
        assert backend.request("protocol.version", timeout=10) == {"version": 1}
        workflow.request(
            "session.create", {"launch_spec": _mock_spec(tmp_path, "w1")}, timeout=30
        )
        info = backend.request("runtime.info", timeout=10)
        assert backend.pid == workflow.pid == info["pid"] == service.proc.pid
        assert info["transport"] == "socket"
        assert sorted(c["label"] for c in info["connections"]) == ["backend", "workflow"]

        # Run end: the workflow releases its own sessions; the runtime stays up.
        workflow.close()
        assert not workflow.connected
        info = backend.request("runtime.info", timeout=10)
        assert info["sessions"] == []
        assert [c["label"] for c in info["connections"]] == ["backend"]
        assert service.proc.poll() is None
    finally:
        backend.close()
        workflow.close()


@posix_only
def test_crashed_client_sessions_are_released(service: _Service, tmp_path: Path) -> None:
    observer = PiRuntimeClient(PROJECT_ROOT, socket_file=service.sock, private=False)
    crashed = PiRuntimeClient(PROJECT_ROOT, socket_file=service.sock, private=False)
    try:
        crashed.request("session.create", {"launch_spec": _mock_spec(tmp_path, "c1")}, timeout=30)
        assert len(observer.request("runtime.info", timeout=10)["sessions"]) == 1
        conn = crashed._conn
        assert conn is not None
        conn.close(0)  # no release_all: like a killed workflow.py
        assert _wait(lambda: observer.request("runtime.info", timeout=10)["sessions"] == [], 5)
    finally:
        observer.close()


@posix_only
def test_client_reconnects_after_runtime_restart(service: _Service) -> None:
    client = PiRuntimeClient(PROJECT_ROOT, socket_file=service.sock, private=False)
    try:
        first = client.request("runtime.info", timeout=10)["pid"]
        service.stop()
        service.start()  # e.g. npm run restart
        info = client.request("runtime.info", timeout=10)
        assert info["pid"] != first
        assert info["pid"] == service.proc.pid
    finally:
        client.close()


@posix_only
def test_diagnostics_check_uses_running_runtime(service: _Service, tmp_path: Path) -> None:
    ok, message = check("pi", project_root=PROJECT_ROOT, socket_file=service.sock)
    assert ok, message
    assert f"pid {service.proc.pid}" in message and "mode=mock" in message
    ok, message = check("pi", project_root=PROJECT_ROOT, socket_file=tmp_path / "none.sock")
    assert not ok and NOT_RUNNING in message


@pytest.mark.skipif(os.name == "nt", reason="POSIX process checks")
def test_private_runtime_exits_on_stdin_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test-only private stdio runtime still never outlives its host."""
    monkeypatch.setenv("PI_RUNTIME_MOCK", "1")
    runtime = PiRuntimeClient(PROJECT_ROOT, private=True)
    try:
        info = runtime.request("runtime.info", timeout=30)
        assert info["mode"] == "mock" and info["transport"] == "stdio"
        pid = runtime.pid
        assert pid
        runtime.close()
        assert _gone(pid)
        assert runtime.pid is None
    finally:
        runtime.close(grace=2)


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


def test_launch_spec_passes_openlca_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP servers live under the long-lived runtime: openLCA settings ride per session."""
    from backend.core.runtime.launch_spec import openlca_env

    monkeypatch.delenv("OPENLCA_IPC_HOST", raising=False)
    monkeypatch.setenv("OPENLCA_IPC_PORT", "9000")
    assert openlca_env(tmp_path) == {"OPENLCA_IPC_PORT": "9000"}
    (tmp_path / ".env").write_text("OPENLCA_IPC_PORT=8181\n", encoding="utf-8")
    assert openlca_env(tmp_path) == {"OPENLCA_IPC_PORT": "8181"}


def test_env_module_prints_runtime_env(tmp_path: Path) -> None:
    """dev.mjs computes the runtime's whitelisted env with `python -m backend.pi_client.env`."""
    import json
    import sys

    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(PROJECT_ROOT / "src"), "CURSOR_SANDBOX": "1"}
    out = subprocess.run(
        [sys.executable, "-m", "backend.pi_client.env", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        cwd=str(PROJECT_ROOT),
    ).stdout
    printed = json.loads(out.strip().splitlines()[-1])
    assert "CURSOR_SANDBOX" not in printed
    assert printed["UV_CACHE_DIR"] == str((tmp_path / ".uv-cache").resolve())
