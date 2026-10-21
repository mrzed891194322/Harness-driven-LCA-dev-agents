"""Runtime error types shared by the pi-runtime client and its callers."""

from __future__ import annotations


class SessionError(Exception):
    """Raised when a session cannot be created or a turn cannot run."""


class WorkerTransportError(SessionError):
    """Worker turn failed before substantive model output (retryable)."""

    def __init__(self, message: str = "", *, outcome: dict | None = None) -> None:
        super().__init__(message)
        self.outcome = dict(outcome or {})
