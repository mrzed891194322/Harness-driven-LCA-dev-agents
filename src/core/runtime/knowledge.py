"""Knowledge providers enrich worker run context."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .context import RunContext

KnowledgeEnrichFn = Callable[[RunContext, Any], dict[str, Any]]


class KnowledgeProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, KnowledgeEnrichFn] = {}

    def register(self, provider_id: str, enrich: KnowledgeEnrichFn) -> None:
        if provider_id in self._providers:
            raise ValueError(f"duplicate knowledge provider {provider_id}")
        self._providers[provider_id] = enrich

    def known_ids(self) -> frozenset[str]:
        return frozenset(self._providers)

    def enrich(self, ctx: RunContext, bundle: Any, provider_id: str) -> dict[str, Any]:
        fn = self._providers.get(provider_id)
        if fn is None:
            raise ValueError(f"unknown knowledge provider {provider_id}")
        return fn(ctx, bundle)
