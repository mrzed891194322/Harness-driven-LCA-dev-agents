"""Registered deterministic checkers invoked by the orchestrator."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .context import RunContext

ValidationStateFn = Callable[[RunContext], dict[str, Any]]
RunValidateFn = Callable[[RunContext], dict[str, Any]]


class CheckerRegistry:
    def __init__(self) -> None:
        self._validation: dict[str, ValidationStateFn] = {}
        self._validate: dict[str, RunValidateFn] = {}

    def register(
        self,
        checker_id: str,
        *,
        validation_state: ValidationStateFn,
        run_validate: RunValidateFn,
    ) -> None:
        if checker_id in self._validation:
            raise ValueError(f"duplicate checker {checker_id}")
        self._validation[checker_id] = validation_state
        self._validate[checker_id] = run_validate

    def known_ids(self) -> frozenset[str]:
        return frozenset(self._validation)

    def validation_state(self, ctx: RunContext, checker_id: str) -> dict[str, Any]:
        fn = self._validation.get(checker_id)
        if fn is None:
            raise ValueError(f"unknown checker {checker_id}")
        return fn(ctx)

    def run_validate(self, ctx: RunContext, checker_id: str) -> dict[str, Any]:
        fn = self._validate.get(checker_id)
        if fn is None:
            raise ValueError(f"unknown checker {checker_id}")
        return fn(ctx)
