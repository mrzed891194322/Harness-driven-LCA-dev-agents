"""Aggregate harness capability registries."""

from __future__ import annotations

from dataclasses import dataclass

from .checkers import CheckerRegistry
from .hooks import HookRegistry
from .knowledge import KnowledgeProviderRegistry
from .knowledge_providers.local_files import register_local_files


@dataclass
class HarnessCapabilities:
    checkers: CheckerRegistry
    knowledge: KnowledgeProviderRegistry
    hooks: HookRegistry


def empty_capabilities() -> HarnessCapabilities:
    """Domain-agnostic empty registries (no providers). Prefer base_capabilities()."""
    return HarnessCapabilities(
        checkers=CheckerRegistry(),
        knowledge=KnowledgeProviderRegistry(),
        hooks=HookRegistry(),
    )


def base_capabilities() -> HarnessCapabilities:
    """Built-in generic providers available to every workflow composition."""
    caps = empty_capabilities()
    register_local_files(caps.knowledge)
    return caps
