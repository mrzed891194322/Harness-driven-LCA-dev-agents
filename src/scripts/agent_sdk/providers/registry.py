"""Worker dispatcher with per-process provider cache."""

from __future__ import annotations

from ..session import SessionClient, SessionConfig, SessionError, SessionRef, TurnResult

WORKERS = ("codex", "claude", "opencode", "pi")


class ProviderDispatcher:
    def __init__(self) -> None:
        self._providers: dict[str, SessionClient] = {}

    def create(self, config: SessionConfig) -> SessionRef:
        return self._provider(config.worker).create(config)

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        if ref.platform != config.worker:
            raise SessionError(
                f"session platform {ref.platform} does not match worker {config.worker}"
            )
        return self._provider(config.worker).resume(ref, config)

    def run_turn(
        self,
        ref: SessionRef,
        prompt: str,
        config: SessionConfig,
    ) -> TurnResult:
        return self._provider(config.worker).run_turn(ref, prompt, config)

    def release(self, ref: SessionRef) -> None:
        self._provider(ref.platform).release(ref)

    def _provider(self, worker: str) -> SessionClient:
        name = (worker or "").strip().lower()
        cached = self._providers.get(name)
        if cached is not None:
            return cached
        created = _new_provider(name)
        self._providers[name] = created
        return created


def _new_provider(name: str) -> SessionClient:
    if name == "codex":
        from .codex.session import CodexSessionProvider

        return CodexSessionProvider()
    if name == "claude":
        from .claude.session import ClaudeSessionProvider

        return ClaudeSessionProvider()
    if name == "opencode":
        from .opencode.session import OpenCodeSessionProvider

        return OpenCodeSessionProvider()
    if name == "pi":
        from .pi.session import PiSessionProvider

        return PiSessionProvider()
    raise SessionError(f"不支持的 Agent：{name}")
