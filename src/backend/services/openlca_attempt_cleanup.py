"""Runner hook: delete openLCA entities from superseded 04 attempts before first import."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import olca_schema

from backend.core.workflow.workspace.index import (
    record_openlca_cleanup,
    record_openlca_unreachable,
    should_run_openlca_attempt_cleanup,
)
from backend.core.workflow.workspace.layout import accepted as load_accepted
from backend.services.diagnostics_service import openlca_endpoint
from harness.tools.shared.control_openlca.attempt_cleanup import (
    cleanup_prior_attempt_imports,
)
from harness.tools.shared.control_openlca.connection import close_ipc_client, connect_ipc

logger = logging.getLogger(__name__)

_TYPE_MAP = {
    "ProductSystem": olca_schema.ProductSystem,
    "Process": olca_schema.Process,
    "Flow": olca_schema.Flow,
}


def maybe_cleanup_before_openlca_write(
    project_root: Path,
    workspace: Path,
    *,
    stage_id: str,
    role: str,
    attempt: int,
) -> None:
    if not should_run_openlca_attempt_cleanup(
        workspace, stage_id, role=role, attempt=attempt
    ):
        return
    host, port = openlca_endpoint(project_root)
    try:
        client = connect_ipc(host, port, olca_schema.ProductSystem)
    except Exception as exc:
        logger.error("openLCA IPC connect failed before cleanup: %s", exc)
        record_openlca_unreachable(
            workspace,
            stage_id,
            role=role,
            attempt=attempt,
        )
        raise RuntimeError("openlca unreachable") from exc

    def fetch_entity(entity_type: str, entity_id: str) -> dict[str, Any] | None:
        model = _TYPE_MAP.get(entity_type)
        if model is None:
            return None
        try:
            live = client.get(model, entity_id)
        except Exception as exc:
            logger.warning("openlca lookup %s %s: %s", entity_type, entity_id, exc)
            return None
        if live is None:
            return None
        return {
            "name": str(getattr(live, "name", "") or ""),
            "category": getattr(live, "category", None),
        }

    def delete_entity(entity_type: str, entity_id: str, _name: str) -> None:
        model = _TYPE_MAP.get(entity_type)
        if model is None:
            return
        live = client.get(model, entity_id)
        if live is None:
            return
        client.delete(live.to_ref())

    try:
        deleted, skipped = cleanup_prior_attempt_imports(
            workspace,
            stage_id=stage_id,
            current_role=role,
            current_attempt=attempt,
            accepted=load_accepted(workspace, stage_id),
            fetch_entity=fetch_entity,
            delete_entity=delete_entity,
        )
    finally:
        close_ipc_client(client)
    record_openlca_cleanup(
        workspace,
        stage_id,
        role=role,
        attempt=attempt,
        deleted=deleted,
        skipped=skipped,
    )
