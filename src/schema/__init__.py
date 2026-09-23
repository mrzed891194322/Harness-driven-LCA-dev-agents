"""Cross-module data contracts (no runtime logic)."""

from .session import (
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
]
