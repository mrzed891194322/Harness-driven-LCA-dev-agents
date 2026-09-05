from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from ...runtime import WorkerError, format_event, jsonish, resolve_emit


def run(
    prompt: str,
    *,
    cwd: Path,
    stop_event: threading.Event | None = None,
    emit=None,
) -> None:
    write = resolve_emit(emit)
    try:
        from opencode_ai import Opencode
    except ImportError as exc:
        raise WorkerError("opencode-ai is not installed") from exc

    base_url = os.environ.get("OPENCODE_BASE_URL", "http://127.0.0.1:4096")
    server: subprocess.Popen | None = None
    started_server = False
    if shutil.which("opencode") and not os.environ.get("OPENCODE_BASE_URL"):
        server = subprocess.Popen(
            ["opencode", "serve", "--port", "4096"],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        started_server = True
    client = Opencode(base_url=base_url, timeout=None)
    session_errors: list[str] = []
    try:
        _wait_ready(client, timeout_s=20.0)
        session = _create_session(client, cwd)
        stream = client.event.list()
        listener = threading.Thread(
            target=_drain_events,
            args=(stream, stop_event, write, session_errors),
            daemon=True,
        )
        listener.start()
        abort_watch = threading.Event()
        watcher = threading.Thread(
            target=_watch_stop,
            args=(client, session.id, stop_event, abort_watch),
            daemon=True,
        )
        watcher.start()
        try:
            _chat(client, session.id, prompt)
        finally:
            abort_watch.set()
        if stop_event is not None and stop_event.is_set():
            raise WorkerError("stopped")
        if session_errors:
            raise WorkerError(session_errors[0])
    finally:
        if started_server and server is not None:
            try:
                os.killpg(server.pid, signal.SIGTERM)
            except Exception:
                server.terminate()


def _wait_ready(client, *, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            client.session.list()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise WorkerError(f"opencode serve did not become ready: {last_error}")


def _create_session(client, cwd: Path):
    try:
        return client.session.create(directory=str(cwd))
    except TypeError:
        return client.session.create()


def _chat(client, session_id: str, prompt: str) -> None:
    parts = [{"type": "text", "text": prompt}]
    provider_id = os.environ.get("OPENCODE_PROVIDER", "").strip()
    model_id = os.environ.get("OPENCODE_MODEL", "").strip()
    if not provider_id or not model_id:
        raise WorkerError("OPENCODE_PROVIDER and OPENCODE_MODEL must be set")
    try:
        client.session.chat(
            session_id,
            provider_id=provider_id,
            model_id=model_id,
            parts=parts,
            extra_body={"model": {"providerID": provider_id, "modelID": model_id}},
            timeout=None,
        )
    except TypeError:
        client.session.chat(id=session_id, parts=parts)


def _watch_stop(client, session_id: str, stop_event: threading.Event | None, done: threading.Event) -> None:
    while not done.is_set():
        if stop_event is not None and stop_event.is_set():
            try:
                client.session.abort(session_id)
            except Exception:
                pass
            return
        time.sleep(0.2)


def _drain_events(stream, stop_event, write, session_errors: list[str]) -> None:
    try:
        for event in stream:
            if stop_event is not None and stop_event.is_set():
                return
            text = jsonish(event)
            write(format_event(kind="opencode", text=text))
            if "Model not found" in text or "session.error" in text.lower():
                session_errors.append(text)
    except Exception as exc:
        write(format_event(kind="error", text=str(exc)))
