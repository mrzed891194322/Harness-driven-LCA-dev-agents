"""Aggregate harness capability registries."""

from __future__ import annotations

from dataclasses import dataclass

from .checkers import CheckerRegistry
from .hooks import HookRegistry
from .knowledge import KnowledgeProviderRegistry


@dataclass
class HarnessCapabilities:
    checkers: CheckerRegistry
    knowledge: KnowledgeProviderRegistry
    hooks: HookRegistry


def empty_capabilities() -> HarnessCapabilities:
    """Domain-agnostic empty registries. Domains register at the composition root."""
    return HarnessCapabilities(
        checkers=CheckerRegistry(),
        knowledge=KnowledgeProviderRegistry(),
        hooks=HookRegistry(),
    )
