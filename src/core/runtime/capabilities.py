"""Aggregate harness capability registries (knowledge-only)."""

from __future__ import annotations

from dataclasses import dataclass

from .knowledge import KnowledgeProviderRegistry
from .knowledge_providers.local_files import register_local_files


@dataclass
class HarnessCapabilities:
    knowledge: KnowledgeProviderRegistry


def empty_capabilities() -> HarnessCapabilities:
    """Domain-agnostic empty registries (no providers). Prefer base_capabilities()."""
    return HarnessCapabilities(knowledge=KnowledgeProviderRegistry())


def base_capabilities() -> HarnessCapabilities:
    """Built-in generic providers available to every workflow composition."""
    caps = empty_capabilities()
    register_local_files(caps.knowledge)
    return caps
