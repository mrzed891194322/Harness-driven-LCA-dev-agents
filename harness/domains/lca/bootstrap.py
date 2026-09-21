"""Register all LCA domain capabilities."""

from __future__ import annotations

from harness.runtime.capabilities import HarnessCapabilities, base_capabilities
from harness.runtime.checkers import CheckerRegistry
from harness.runtime.hooks import HookRegistry
from harness.runtime.knowledge import KnowledgeProviderRegistry

from .checkers import register_lca_checkers
from .hooks import register_lca_hooks
from .knowledge import register_lca_knowledge


def register_lca(
    checkers: CheckerRegistry,
    knowledge: KnowledgeProviderRegistry,
    hooks: HookRegistry,
) -> None:
    register_lca_checkers(checkers)
    register_lca_knowledge(knowledge)
    register_lca_hooks(hooks)


def lca_capabilities() -> HarnessCapabilities:
    """Composition helper: base (local_files) + LCA domain capabilities."""
    caps = base_capabilities()
    register_lca(caps.checkers, caps.knowledge, caps.hooks)
    return caps
