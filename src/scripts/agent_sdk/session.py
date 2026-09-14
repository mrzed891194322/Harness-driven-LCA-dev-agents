"""Unified worker session types and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class SessionError(Exception):
    """Raised when a session cannot be created or a turn cannot run."""


class SessionResumeError(SessionError):
    """Raised when the original session or its storage cannot be restored."""


@dataclass
class SessionRef:
    platform: str
    session_id: str
    storage: dict[str, str] = field(default_factory=dict)
    last_turn_status: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "session_id": self.session_id,
            "storage": dict(self.storage),
            "last_turn_status": self.last_turn_status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SessionRef:
        return cls(
            platform=str(payload["platform"]),
            session_id=str(payload["session_id"]),
            storage={
                str(k): str(v) for k, v in dict(payload.get("storage") or {}).items()
            },
            last_turn_status=str(payload.get("last_turn_status") or "ok"),
        )


@dataclass
class SessionConfig:
    """Backend-agnostic turn payload. Providers consume this; they do not read YAML."""

    worker: str
    cwd: Path
    tmp_dir: Path
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)
    model: str = ""
    spec_paths: list[str] = field(default_factory=list)
    rule_ids: list[str] = field(default_factory=list)
    tool_ids: list[str] = field(default_factory=list)
    stage_id: str = ""
    role: str = ""
    attempt: int = 0
    run_id: str = ""
    mcp_render_dir: Path | None = None
    archive_dir: Path | None = None


@dataclass
class TurnResult:
    status: str
    session_ref: SessionRef
    text: str = ""


class SessionClient(Protocol):
    def create(self, config: SessionConfig) -> SessionRef:
        """Create a new worker session and return a serializable reference."""
        ...

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        """Restore an existing session. Must fail if storage is missing."""
        ...

    def run_turn(
        self,
        ref: SessionRef,
        prompt: str,
        config: SessionConfig,
    ) -> TurnResult:
        """Send one turn to the session."""
        ...

    def release(self, ref: SessionRef) -> None:
        """Close live connections; keep native session storage."""
        ...


def default_client() -> SessionClient:
    from .providers import ProviderDispatcher

    return ProviderDispatcher()
