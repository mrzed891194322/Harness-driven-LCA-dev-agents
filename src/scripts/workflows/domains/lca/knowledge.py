"""LCA knowledge registration (local_files comes from base_capabilities)."""

from __future__ import annotations

from scripts.workflows.runtime.knowledge import KnowledgeProviderRegistry
from scripts.workflows.runtime.knowledge_providers.local_files import (
    PROVIDER_ID,
    discover_files_at,
    enrich_local_files,
)

__all__ = [
    "PROVIDER_ID",
    "discover_files_at",
    "enrich_local_files",
    "register_lca_knowledge",
]


def register_lca_knowledge(registry: KnowledgeProviderRegistry) -> None:
    """LCA-specific knowledge providers (none yet; local_files is base)."""
    del registry
