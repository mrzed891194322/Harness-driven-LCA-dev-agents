"""Register service-layer hooks with the core orchestrator."""

from __future__ import annotations

from backend.core.workflow.hooks import set_before_openlca_write


def install() -> None:
    from backend.services.openlca_attempt_cleanup import maybe_cleanup_before_openlca_write

    set_before_openlca_write(maybe_cleanup_before_openlca_write)
