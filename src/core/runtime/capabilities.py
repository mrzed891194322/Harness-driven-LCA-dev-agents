"""Aggregate harness capability registries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .checkers import CheckerRegistry
from .context import RunContext
from .hooks import HookRegistry
from .knowledge import KnowledgeProviderRegistry
from .knowledge_providers.local_files import register_local_files


@dataclass
class HarnessCapabilities:
    checkers: CheckerRegistry
    knowledge: KnowledgeProviderRegistry
    hooks: HookRegistry
    handoff_validators: list[Callable[[RunContext, dict[str, Any]], None]] = field(
        default_factory=list
    )


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
