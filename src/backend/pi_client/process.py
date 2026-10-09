"""Client for the project's single pi-runtime (NDJSON protocol).

Lifetime (ISSUES #23, Du Yuan's rule): exactly ONE pi-runtime per project. It is
a service started by ``npm run dev`` / ``npm start`` and stopped by
``npm run stop``; it listens on a Unix domain socket
(``.local/run/pi-runtime.sock``, override with ``PI_RUNTIME_SOCKET``). The
backend and every workflow.py subprocess connect to it -- they never spawn one.
Closing a connection releases the sessions (and MCP servers) it created; the
runtime itself stays up.

``PI_RUNTIME_PRIVATE=1`` (tests only) spawns a private stdio child instead.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import socket
import subprocess
import sys
import threading
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from backend.core.agents.session import SessionError
from backend.core.agents.turn_transport import WorkerTransportError

from .env import runtime_env

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)

SOCKET_ENV = "PI_RUNTIME_SOCKET"
PRIVATE_ENV = "PI_RUNTIME_PRIVATE"
NOT_RUNNING = "pi-runtime 未运行，请用 npm run dev 启动"

EventHandler = Callable[[str, dict[str, Any]], None]

# Runtime errors whose message looks like a network/model-endpoint outage are
# retryable; everything else (bad params, unknown session, model refusal,
# missing files) is surfaced as-is so it is not misreported as a connection issue.
_TRANSIENT_RUNTIME_ERROR = re.compile(
    r"ECONNREFUSED|ECONNRESET|ETIMEDOUT|EAI_AGAIN|ENOTFOUND|EPIPE|socket hang up"
    r"|fetch failed|network|timed? ?out|\b(429|500|502|503|504)\b|overloaded"
    r"|rate.?limit",
    re.IGNORECASE,
)


def runtime_error(message: str) -> Exception:
    if _TRANSIENT_RUNTIME_ERROR.search(message):
        return WorkerTransportError(message)
    return SessionError(message)


class RuntimeNotRunning(SessionError):
    """The project's pi-runtime service is not listening (not retryable)."""


def socket_path(project_root: Path | None = None) -> Path:
    """Where the project's pi-runtime listens."""
    override = (os.environ.get(SOCKET_ENV) or "").strip()
    if override:
        return Path(override).expanduser()
    return (project_root or PROJECT_ROOT) / ".local" / "run" / "pi-runtime.sock"


def runtime_entry(project_root: Path) -> list[str]:
    """``node`` argv for pi-runtime (built dist, else tsx on the sources)."""
    rt = project_root / "src" / "pi-runtime"
    dist = rt / "dist" / "main.js"
    if dist.is_file():
        return ["node", str(dist)]
    src = rt / "src" / "main.ts"
    for base in (rt, project_root):
        tsx = base / "node_modules" / "tsx" / "dist" / "esm" / "index.js"
        if tsx.is_file():
            return ["node", "--import", str(tsx), str(src)]
    return ["node", "--import", "tsx", str(src)]


class _Connection:
    """One NDJSON byte stream to a runtime."""

    def send(self, line: str) -> None:
        raise NotImplementedError

    def lines(self) -> Iterator[str]:
        raise NotImplementedError

    def close(self, grace: float) -> None:
        raise NotImplementedError

    @property
    def pid(self) -> int | None:
        return None


class _SocketConnection(_Connection):
    def __init__(self, path: Path, timeout: float = 5.0) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(str(path))
        except OSError:
            sock.close()
            raise
        sock.settimeout(None)
        self._sock = sock
        self._reader = sock.makefile("r", encoding="utf-8", newline="\n")
        self._write_lock = threading.Lock()

    def send(self, line: str) -> None:
        with self._write_lock:
            self._sock.sendall(line.encode("utf-8"))

    def lines(self) -> Iterator[str]:
        yield from self._reader

    def close(self, grace: float) -> None:
        del grace
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._sock.close()


class _PrivateProcess(_Connection):
    """Private stdio runtime (tests only): exits when its stdin closes."""

    def __init__(self, project_root: Path) -> None:
        log_dir = project_root / ".local" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "pi-runtime.log", "a", encoding="utf-8") as stderr_log:
            self._proc = subprocess.Popen(
                runtime_entry(project_root),
                cwd=str(project_root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr_log,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=runtime_env(project_root),
            )
        self._write_lock = threading.Lock()

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc.poll() is None else None

    @property
    def process(self) -> subprocess.Popen[str]:
        return self._proc

    def send(self, line: str) -> None:
        assert self._proc.stdin is not None
        with self._write_lock:
            self._proc.stdin.write(line)
            self._proc.stdin.flush()

    def lines(self) -> Iterator[str]:
        assert self._proc.stdout is not None
        yield from self._proc.stdout

    def close(self, grace: float) -> None:
        proc = self._proc
        if proc.poll() is not None:
            return
        try:
            if proc.stdin is not None:
                proc.stdin.close()  # runtime: dispose sessions, then exit(0)
        except OSError:
            pass
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


class PiRuntimeClient:
    """Connection to the project's pi-runtime.

    Connects lazily on the first request and reconnects once if the connection
    broke. It never starts a runtime (unless ``private`` / ``PI_RUNTIME_PRIVATE=1``).
    ``close()`` drops the connection: the runtime releases this client's
    sessions and their MCP servers, and keeps running for everyone else.
    """

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        socket_file: Path | None = None,
        private: bool | None = None,
        label: str | None = None,
    ) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self._socket = socket_file
        self.private = (
            os.environ.get(PRIVATE_ENV) == "1" if private is None else private
        )
        self.label = label or f"{Path(sys.argv[0] or 'python').name} pid={os.getpid()}"
        self._conn: _Connection | None = None
        self._lock = threading.Lock()
        self._connect_lock = threading.Lock()
        self._pending: dict[str, threading.Event] = {}
        self._responses: dict[str, dict[str, Any]] = {}
        self._event_handlers: list[EventHandler] = []
        self.runtime_pid: int | None = None

    @property
    def socket_path(self) -> Path:
        return self._socket or socket_path(self.project_root)

    def add_event_handler(self, handler: EventHandler) -> None:
        with self._lock:
            self._event_handlers.append(handler)

    def remove_event_handler(self, handler: EventHandler) -> None:
        with self._lock:
            try:
                self._event_handlers.remove(handler)
            except ValueError:
                pass

    @property
    def connected(self) -> bool:
        return self._conn is not None

    @property
    def pid(self) -> int | None:
        """pid of the runtime this client talks to (None when not connected)."""
        conn = self._conn
        if conn is None:
            return None
        if isinstance(conn, _PrivateProcess):
            return conn.pid
        return self.runtime_pid

    def start(self) -> None:
        """Connect (or, in private mode, spawn) if not connected yet."""
        self._ensure_connected()

    def _ensure_connected(self) -> _Connection:
        with self._connect_lock:
            conn = self._conn
            if conn is not None:
                return conn
            conn = self._open()
            with self._lock:
                self._conn = conn
            threading.Thread(target=self._read_loop, args=(conn,), daemon=True).start()
        if not self.private:
            try:
                info = self._call(conn, "client.hello", {"label": self.label}, timeout=10.0)
                if isinstance(info, dict) and info.get("pid"):
                    self.runtime_pid = int(info["pid"])
            except Exception:  # noqa: BLE001 - an old runtime may not know hello
                pass
        return conn

    def _open(self) -> _Connection:
        if self.private:
            return _PrivateProcess(self.project_root)
        path = self.socket_path
        try:
            return _SocketConnection(path)
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            raise RuntimeNotRunning(f"{NOT_RUNNING}（{path}）") from exc
        except OSError as exc:
            raise RuntimeNotRunning(f"{NOT_RUNNING}（连接 {path} 失败：{exc}）") from exc

    def _drop(self, conn: _Connection, message: str, *, grace: float = 10.0) -> None:
        with self._lock:
            if self._conn is conn:
                self._conn = None
        try:
            conn.close(grace)
        except OSError:
            pass
        self._fail_pending(conn, message)

    def _read_loop(self, conn: _Connection) -> None:
        try:
            for line in conn.lines():
                self._dispatch(line)
        except (OSError, ValueError):
            pass
        finally:
            with self._lock:
                current = self._conn is conn
                if current:
                    self._conn = None
            if current:
                self._fail_pending(conn, "pi-runtime 连接已断开")

    def _dispatch(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return
        kind = payload.get("type")
        if kind == "res":
            req_id = str(payload.get("id") or "")
            with self._lock:
                event = self._pending.pop(req_id, None)
                if event is not None:
                    self._responses[req_id] = payload
            if event:
                event.set()
        elif kind == "event":
            name = str(payload.get("event") or "")
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            if name == "ready" and data.get("pid"):
                try:
                    self.runtime_pid = int(data["pid"])
                except (TypeError, ValueError):
                    pass
            with self._lock:
                handlers = list(self._event_handlers)
            for handler in handlers:
                try:
                    handler(name, data)
                except Exception:
                    pass

    def _fail_pending(self, conn: _Connection, message: str) -> None:
        """Wake every waiter of a dead connection instead of letting it time out."""
        del conn  # one connection at a time: everything pending belonged to it
        with self._lock:
            pending = list(self._pending.items())
            self._pending.clear()
            for req_id, _event in pending:
                self._responses[req_id] = {
                    "ok": False,
                    "error": {"code": "runtime_disconnected", "message": message},
                }
        for _req_id, event in pending:
            event.set()

    def _call(
        self, conn: _Connection, method: str, params: dict[str, Any], *, timeout: float
    ) -> Any:
        req_id = uuid.uuid4().hex
        event = threading.Event()
        with self._lock:
            self._pending[req_id] = event
        line = json.dumps(
            {"type": "req", "id": req_id, "method": method, "params": params},
            ensure_ascii=False,
        )
        try:
            conn.send(line + "\n")
        except OSError:
            with self._lock:
                self._pending.pop(req_id, None)
            raise
        if not event.wait(timeout):
            with self._lock:
                self._pending.pop(req_id, None)
            raise WorkerTransportError(f"pi-runtime 请求超时: {method}")
        with self._lock:
            payload = self._responses.pop(req_id, {})
        if not payload.get("ok"):
            err = payload.get("error") or {}
            raise runtime_error(str(err.get("message") or "pi-runtime 错误"))
        return payload.get("result")

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 600.0,
    ) -> Any:
        conn = self._ensure_connected()
        try:
            return self._call(conn, method, params or {}, timeout=timeout)
        except OSError as first:
            # Stale connection (runtime restarted by npm run restart): reconnect once.
            self._drop(conn, "pi-runtime 连接已断开")
            conn = self._ensure_connected()
            try:
                return self._call(conn, method, params or {}, timeout=timeout)
            except OSError as exc:
                self._drop(conn, "pi-runtime 连接已断开")
                raise WorkerTransportError(f"pi-runtime 写入失败: {exc}") from first

    def close(self, *, grace: float = 10.0) -> None:
        """Release this client's sessions (MCP servers) and disconnect.

        The shared runtime keeps running. In private mode the child is stopped.
        """
        conn = self._conn
        if conn is None:
            return
        if not self.private:
            try:
                self._call(conn, "session.release_all", {}, timeout=30.0)
            except Exception:  # noqa: BLE001 - disconnect releases them anyway
                pass
        self._drop(conn, "pi-runtime 连接已关闭", grace=grace)


# One connection per Python process (backend API, or one workflow.py run).
_RUNTIME: PiRuntimeClient | None = None
_RUNTIME_LOCK = threading.Lock()


def shared_runtime(project_root: Path | None = None) -> PiRuntimeClient:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = PiRuntimeClient(project_root)
            atexit.register(close_shared_runtime)
        return _RUNTIME


def close_shared_runtime() -> None:
    """Release this process's sessions and disconnect (idempotent).

    Does NOT stop the project's runtime: only ``npm run stop`` does that.
    """
    runtime = _RUNTIME
    if runtime is not None:
        runtime.close()
