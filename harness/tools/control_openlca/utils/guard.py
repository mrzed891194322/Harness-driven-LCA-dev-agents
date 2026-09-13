"""Cross-process endpoint ownership; HTTP timeouts do not cancel server work."""

from __future__ import annotations

import functools
import getpass
import hashlib
import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import requests

from .connection import (
    build_endpoint,
    close_ipc_client,
    is_transport_error,
    probe_ipc,
    session_budget_sec,
)

_local = threading.local()


def remaining_budget():
    deadline = getattr(_local, "deadline", None)
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise requests.Timeout(
            "IPC call deadline exhausted; no further request submitted"
        )
    return remaining


@contextmanager
def cleanup_budget():
    """Reserve a bounded disposal attempt after the main request budget expires."""
    previous = getattr(_local, "deadline", None)
    if previous is not None:
        _local.deadline = time.monotonic() + 10.0
    try:
        yield
    finally:
        _local.deadline = previous


class EndpointBusy(RuntimeError):
    pass


def _transport_failure(exc):
    while exc is not None:
        if is_transport_error(exc):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


@contextmanager
def file_lock(path: Path, timeout: float = 5.0):
    """OS-owned locks survive neither process death nor descriptor closure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        if stream.read(1) == b"":
            stream.write(b"0")
            stream.flush()
        started = time.monotonic()
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() - started >= timeout:
                    raise EndpointBusy(
                        "endpoint busy: lock wait exceeded deadline"
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def endpoint_guard(host: str, port: int, *, budget_sec: float | None = None):
    endpoint = build_endpoint(host, port)
    held = getattr(_local, "held", set())
    if endpoint in held:
        yield
        return
    user = hashlib.sha256(getpass.getuser().encode()).hexdigest()[:16]
    root = Path(
        os.getenv(
            "LCA_IPC_LOCK_ROOT", str(Path(tempfile.gettempdir()) / f"lca-ipc-{user}")
        )
    )
    key = hashlib.sha256(endpoint.encode()).hexdigest()
    uncertain = root / f"{key}.uncertain"
    waiting_at = time.monotonic()
    with file_lock(root / f"{key}.lock"):
        _local.lock_wait_ms = round((time.monotonic() - waiting_at) * 1000)
        if uncertain.exists():
            client = None
            try:
                client = probe_ipc(host, port)
            except Exception as exc:
                raise EndpointBusy(
                    "previous IPC operation is uncertain; bounded probe failed"
                ) from exc
            finally:
                close_ipc_client(client)
        # A process killed while holding the lock leaves this marker behind.
        uncertain.write_text(json.dumps({"pid": os.getpid(), "endpoint": endpoint}))
        _local.held = held | {endpoint}
        deadline_sec = (
            budget_sec
            if budget_sec is not None
            else session_budget_sec(long_running=False)
        )
        _local.deadline = time.monotonic() + deadline_sec
        try:
            yield
        except BaseException as exc:
            if isinstance(exc, Exception) and not _transport_failure(exc):
                uncertain.unlink(missing_ok=True)
            raise
        else:
            if not getattr(_local, "uncertain", False):
                uncertain.unlink(missing_ok=True)
        finally:
            _local.held = held
            _local.uncertain = False
            _local.deadline = None


def mark_uncertain():
    _local.uncertain = True


def serialized_ipc(function=None, *, long_running: bool = False):
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(host, port, *args, **kwargs):
            budget = session_budget_sec(long_running=long_running)
            with endpoint_guard(host, port, budget_sec=budget):
                result = fn(host, port, *args, **kwargs)
                if isinstance(result, dict):
                    result["lock_wait_ms"] = getattr(_local, "lock_wait_ms", 0)
                # Some existing domain services preserve failures in result dictionaries.
                text = json.dumps(result, default=str).lower()
                if any(
                    word in text
                    for word in (
                        "timed out",
                        "timeout",
                        "connectionerror",
                        "connection refused",
                    )
                ):
                    if isinstance(result, dict) and (
                        result.get("errors")
                        or result.get("error")
                        or result.get("ok") is False
                    ):
                        mark_uncertain()
                return result

        return wrapped

    if function is not None:
        return decorate(function)
    return decorate
