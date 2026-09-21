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


def default_capabilities() -> HarnessCapabilities:
    from harness.domains.lca.bootstrap import register_lca

    checkers = CheckerRegistry()
    knowledge = KnowledgeProviderRegistry()
    hooks = HookRegistry()
    register_lca(checkers, knowledge, hooks)
    return HarnessCapabilities(checkers=checkers, knowledge=knowledge, hooks=hooks)
