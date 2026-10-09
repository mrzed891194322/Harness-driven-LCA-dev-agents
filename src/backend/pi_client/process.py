"""Managed Node pi-runtime subprocess (NDJSON protocol)."""

from __future__ import annotations

import atexit
import json
import re
import subprocess
import threading
import uuid
from collections.abc import Callable
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


class PiRuntimeProcess:
    """Single long-lived pi-runtime child process.

    Lifetime: the runtime exits by itself when its stdin closes, so ``shutdown()``
    closes stdin first (the runtime then disposes every session, which stops its
    MCP servers) and only escalates to SIGTERM / SIGKILL if it does not exit.
    After ``shutdown()`` the next ``request()`` starts a fresh runtime.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._pending: dict[str, threading.Event] = {}
        self._responses: dict[str, dict[str, Any]] = {}
        self._reader: threading.Thread | None = None
        self._event_handlers: list[EventHandler] = []

    def add_event_handler(self, handler: EventHandler) -> None:
        with self._lock:
            self._event_handlers.append(handler)

    def remove_event_handler(self, handler: EventHandler) -> None:
        with self._lock:
            try:
                self._event_handlers.remove(handler)
            except ValueError:
                pass

    def start(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return
            runtime_js = self._runtime_entry()
            env = runtime_env(self.project_root)
            log_dir = self.project_root / ".local" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            stderr_log = open(log_dir / "pi-runtime.log", "a", encoding="utf-8")
            self._proc = subprocess.Popen(
                runtime_js,
                cwd=str(self.project_root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr_log,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=env,
            )
            stderr_log.close()  # the child holds its own descriptor
            self._reader = threading.Thread(
                target=self._read_loop, args=(self._proc,), daemon=True
            )
            self._reader.start()

    @property
    def pid(self) -> int | None:
        proc = self._proc
        return proc.pid if proc is not None and proc.poll() is None else None

    def _runtime_entry(self) -> list[str]:
        rt = self.project_root / "src" / "pi-runtime"
        dist = rt / "dist" / "main.js"
        if dist.is_file():
            return ["node", str(dist)]
        src = rt / "src" / "main.ts"
        tsx = rt / "node_modules" / "tsx" / "dist" / "esm" / "index.js"
        if tsx.is_file():
            return ["node", "--import", str(tsx), str(src)]
        return ["node", "--import", "tsx", str(src)]

    def _read_loop(self, proc: subprocess.Popen[str]) -> None:
        if proc.stdout is None:
            return
        try:
            self._pump(proc)
        except (OSError, ValueError):
            pass
        finally:
            with self._lock:
                current = self._proc is proc or self._proc is None
            if current:
                self._fail_pending("pi-runtime 已退出")

    def _fail_pending(self, message: str) -> None:
        """Wake every waiter when the runtime goes away instead of letting it time out."""
        with self._lock:
            pending = list(self._pending.items())
            self._pending.clear()
            for req_id, _event in pending:
                self._responses[req_id] = {
                    "ok": False,
                    "error": {"code": "runtime_exited", "message": message},
                }
        for _req_id, event in pending:
            event.set()

    def _pump(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = payload.get("type")
            if kind == "res":
                req_id = str(payload.get("id") or "")
                with self._lock:
                    self._responses[req_id] = payload
                    event = self._pending.pop(req_id, None)
                    handlers = list(self._event_handlers)
                if event:
                    event.set()
            elif kind == "event":
                name = str(payload.get("event") or "")
                data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
                with self._lock:
                    handlers = list(self._event_handlers)
                for handler in handlers:
                    try:
                        handler(name, data)
                    except Exception:
                        pass

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 600.0,
    ) -> Any:
        self.start()
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise WorkerTransportError("pi-runtime 未启动")
        req_id = uuid.uuid4().hex
        event = threading.Event()
        with self._lock:
            self._pending[req_id] = event
        message = {
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params or {},
        }
        try:
            proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            proc.stdin.flush()
        except OSError as exc:
            raise WorkerTransportError(f"pi-runtime 写入失败: {exc}") from exc
        if not event.wait(timeout):
            raise WorkerTransportError(f"pi-runtime 请求超时: {method}")
        with self._lock:
            payload = self._responses.pop(req_id, {})
        if not payload.get("ok"):
            err = payload.get("error") or {}
            raise runtime_error(str(err.get("message") or "pi-runtime 错误"))
        return payload.get("result")

    def shutdown(self, *, grace: float = 10.0) -> None:
        """Stop the runtime and, through it, every session's MCP servers."""
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is None:
            return
        if proc.poll() is None:
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
        self._fail_pending("pi-runtime 已关闭")


# One runtime per Python process. The backend API process and the workflow
# orchestrator subprocess (src/scripts/workflow.py) are different processes, so
# each has its own runtime while a run is active; the orchestrator's runtime is
# shut down when the run ends (ISSUES #23).
_RUNTIME: PiRuntimeProcess | None = None
_RUNTIME_LOCK = threading.Lock()


def shared_runtime(project_root: Path | None = None) -> PiRuntimeProcess:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = PiRuntimeProcess(project_root)
            atexit.register(shutdown_shared_runtime)
        return _RUNTIME


def shutdown_shared_runtime() -> None:
    """Stop this process's runtime if one was started (idempotent)."""
    runtime = _RUNTIME
    if runtime is not None:
        runtime.shutdown()
