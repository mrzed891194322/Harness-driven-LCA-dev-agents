"""Per-request IPC read timeouts (independent of shrinking session budget)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar

DEFAULT_REQUEST_READ_SEC = 120.0
DEFAULT_PRODUCT_SYSTEM_READ_SEC = 300.0
DEFAULT_HEALTH_PROBE_SEC = 10.0
DEFAULT_CONNECT_SEC = 2.0

_ipc_read_sec: ContextVar[float | None] = ContextVar("ipc_read_sec", default=None)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def request_read_sec() -> float:
    return _env_float("OPENLCA_TIMEOUT_REQUEST_S", DEFAULT_REQUEST_READ_SEC)


def product_system_read_sec() -> float:
    return _env_float(
        "OPENLCA_TIMEOUT_PRODUCT_SYSTEM_S", DEFAULT_PRODUCT_SYSTEM_READ_SEC
    )


def health_probe_sec() -> float:
    return _env_float("OPENLCA_TIMEOUT_HEALTH_PROBE_S", DEFAULT_HEALTH_PROBE_SEC)


def active_read_sec() -> float:
    override = _ipc_read_sec.get()
    if override is not None:
        return override
    return request_read_sec()


@contextmanager
def ipc_read_scope(read_sec: float):
    token = _ipc_read_sec.set(read_sec)
    try:
        yield
    finally:
        _ipc_read_sec.reset(token)


def resolve_http_read_timeout(
    *,
    read_sec: float | None = None,
    connect_sec: float = DEFAULT_CONNECT_SEC,
) -> tuple[float, float]:
    """Return (connect, read) without shrinking read below ``read_sec``."""
    from .guard import remaining_budget

    configured = read_sec if read_sec is not None else active_read_sec()
    remaining = remaining_budget()
    if remaining is None:
        return (connect_sec, configured)
    needed = connect_sec + configured
    if remaining < needed:
        raise __import__("requests").Timeout(
            "IPC session budget insufficient for "
            f"{configured:.1f}s read ({remaining:.2f}s remaining); "
            "fail fast without submitting request"
        )
    connect = min(connect_sec, max(0.001, remaining / 2))
    read = min(configured, max(0.001, remaining - connect))
    return (connect, read)
