"""Managed Node pi-runtime subprocess (NDJSON protocol)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from core.agents.turn_transport import WorkerTransportError

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)


class PiRuntimeProcess:
    """Single long-lived pi-runtime child process."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._pending: dict[str, threading.Event] = {}
        self._responses: dict[str, dict[str, Any]] = {}
        self._reader: threading.Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return
            runtime_js = self._runtime_entry()
            env = os.environ.copy()
            if os.getenv("PI_RUNTIME_MOCK", "").strip() in {"1", "true", "yes"}:
                env["PI_RUNTIME_MOCK"] = "1"
            self._proc = subprocess.Popen(
                runtime_js,
                cwd=str(self.project_root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=env,
            )
            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()

    def _runtime_entry(self) -> list[str]:
        dist = self.project_root / "src" / "pi-runtime" / "dist" / "main.js"
        if dist.is_file():
            return ["node", str(dist)]
        src = self.project_root / "src" / "pi-runtime" / "src" / "main.ts"
        return ["node", "--import", "tsx", str(src)]

    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("type") == "res":
                req_id = str(payload.get("id") or "")
                with self._lock:
                    self._responses[req_id] = payload
                    event = self._pending.pop(req_id, None)
                if event:
                    event.set()
            # events are ignored at this layer; progress hooks can be added later

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
            raise WorkerTransportError(str(err.get("message") or "pi-runtime 错误"))
        return payload.get("result")

    def shutdown(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


_RUNTIME: PiRuntimeProcess | None = None


def shared_runtime(project_root: Path | None = None) -> PiRuntimeProcess:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = PiRuntimeProcess(project_root)
    return _RUNTIME
