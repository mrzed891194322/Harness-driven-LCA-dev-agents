"""Unified worker session dispatcher (types live in schema)."""

from __future__ import annotations

from core.contracts.session import (
    SessionClient,
    SessionConfig,
    SessionError,
    SessionRef,
    SessionResumeError,
    TurnResult,
)

__all__ = [
    "SessionClient",
    "SessionConfig",
    "SessionError",
    "SessionRef",
    "SessionResumeError",
    "TurnResult",
    "default_client",
]


def default_client() -> SessionClient:
    from .providers import ProviderDispatcher

    return ProviderDispatcher()
