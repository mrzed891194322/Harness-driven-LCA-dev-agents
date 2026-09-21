"""LCA knowledge registration (uses generic local_files provider)."""

from __future__ import annotations

from harness.runtime.knowledge import KnowledgeProviderRegistry
from harness.runtime.knowledge_providers.local_files import (
    PROVIDER_ID,
    discover_files_at,
    enrich_local_files,
    register_local_files,
)

__all__ = [
    "PROVIDER_ID",
    "discover_files_at",
    "enrich_local_files",
    "register_lca_knowledge",
]


def register_lca_knowledge(registry: KnowledgeProviderRegistry) -> None:
    register_local_files(registry)
