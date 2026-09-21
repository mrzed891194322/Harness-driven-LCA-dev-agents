"""Lifecycle hooks (e.g. after reviewer passes)."""

from __future__ import annotations

from collections.abc import Callable

from .context import RunContext

HookFn = Callable[[RunContext], None]


class HookRegistry:
    def __init__(self) -> None:
        self._hooks: dict[str, HookFn] = {}

    def register(self, hook_id: str, handler: HookFn) -> None:
        if hook_id in self._hooks:
            raise ValueError(f"duplicate hook {hook_id}")
        self._hooks[hook_id] = handler

    def known_ids(self) -> frozenset[str]:
        return frozenset(self._hooks)

    def run(self, hook_id: str, ctx: RunContext) -> None:
        fn = self._hooks.get(hook_id)
        if fn is None:
            raise ValueError(f"unknown hook {hook_id}")
        fn(ctx)
