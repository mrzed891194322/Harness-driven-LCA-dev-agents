"""Shared openLCA project-category cleanup for MCP and offline tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import olca_schema
import requests

from harness.tools.shared.control_openlca.connection import (
    close_ipc_client,
    create_ipc_client,
    is_transport_error,
    probe_ipc,
)
from harness.tools.shared.control_openlca.ipc_failure import on_ipc_transport_failure
from harness.tools.shared.control_openlca.protocols import (
    OlcaDescriptor,
    OpenLcaClient,
)
from harness.tools.shared.control_openlca.workflow import (
    ENTITY_TYPES,
    load_lci_inventory,
)


logger = logging.getLogger(__name__)


def connect_ipc(host, port, model_type=None):
    """Service-safe connection: errors propagate instead of exiting the MCP process."""
    return create_ipc_client(host, port)


def is_in_project_category(category: str | None, project_name: str) -> bool:
    if not category:
        return False
    return category == project_name or category.startswith(project_name + "/")


class CleanupReadTimeout(RuntimeError):
    """A read-only cleanup query timed out twice (or the health probe failed)."""


def read_with_retry(label: str, call, *, host: str | None, port: int | None):
    """Run a read-only query; on read timeout probe health and retry once.

    Only for idempotent reads (descriptors / get). Deletes never retry.
    """
    try:
        return call()
    except requests.Timeout as first:
        if host is None or port is None:
            raise CleanupReadTimeout(f"{label} 读取超时: {first}") from first
        client = None
        try:
            client = probe_ipc(host, port)
        except Exception as probe_exc:
            raise CleanupReadTimeout(
                f"{label} 读取超时，随后健康探测也失败（openLCA 可能卡死，"
                f"请检查/重启 openLCA）: {probe_exc}"
            ) from first
        finally:
            close_ipc_client(client)
        try:
            return call()
        except requests.Timeout as second:
            raise CleanupReadTimeout(
                f"{label} 读取超时（健康探测正常，已重试 1 次仍超时；"
                f"openLCA 可能在处理大查询或部分卡住）: {second}"
            ) from second


def collect_entities(
    client: OpenLcaClient,
    project_name: str,
    model_types: list[type],
    *,
    host: str | None = None,
    port: int | None = None,
) -> list[tuple[type, OlcaDescriptor]]:
    entities: list[tuple[type, OlcaDescriptor]] = []
    for model_type in model_types:
        try:
            descriptors = read_with_retry(
                f"{model_type.__name__} descriptors",
                lambda model_type=model_type: client.get_descriptors(model_type),
                host=host,
                port=port,
            )
        except CleanupReadTimeout:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Failed to get {model_type.__name__} descriptors; "
                "cleanup scope is incomplete"
            ) from exc

        for descriptor in descriptors:
            if is_in_project_category(
                getattr(descriptor, "category", None),
                project_name,
            ):
                entities.append((model_type, descriptor))
    return entities


def delete_entities(
    client: OpenLcaClient,
    entities: list[tuple[type, OlcaDescriptor]],
    model_types: list[type],
    *,
    project_name: str,
    host: str | None = None,
    port: int | None = None,
) -> tuple[int, list[str]]:
    """Delete entities, re-checking each one is inside ``project_name`` first.

    Defensive: callers already filter, but every target (including supporting
    FlowProperty/UnitGroup) is fetched again and skipped unless its live
    category is the project category. Missing or unverifiable targets are
    skipped, never deleted.
    """
    deleted_count = 0
    errors: list[str] = []
    deleted: list[str] = []
    for model_type in model_types:
        current = [item for item in entities if item[0] == model_type]
        for _, descriptor in current:
            entity_id = str(getattr(descriptor, "id", "") or "")
            label = f"{model_type.__name__} {getattr(descriptor, 'name', '')} ({entity_id})"
            if not entity_id:
                logger.warning("cleanup skip %s: missing @id", label)
                continue
            try:
                live = client.get(model_type, entity_id)
            except Exception as exc:
                logger.warning("cleanup skip %s: lookup failed: %s", label, exc)
                errors.append(f"Skipped {label}: lookup failed, not deleted: {exc}")
                continue
            if live is None:
                logger.info("cleanup skip %s: not found", label)
                continue
            category = getattr(live, "category", None)
            if not is_in_project_category(
                category if isinstance(category, str) else None, project_name
            ):
                logger.warning(
                    "cleanup skip %s: outside project category (%r)", label, category
                )
                errors.append(
                    f"Skipped {label}: outside project category {category!r}, not deleted"
                )
                continue
            try:
                client.delete(descriptor.to_ref())
                deleted_count += 1
                deleted.append(label)
            except Exception as exc:
                errors.append(
                    f"Failed to delete {descriptor.name} ({descriptor.id}): {exc}"
                )
                if is_transport_error(exc) and host is not None and port is not None:
                    on_ipc_transport_failure(
                        host,
                        port,
                        exc,
                        operation="cleanup_delete",
                        entity={
                            "entity_type": model_type.__name__,
                            "id": descriptor.id,
                            "name": descriptor.name,
                        },
                    )
                    logger.info("cleanup deleted %d: %s", deleted_count, deleted)
                    return deleted_count, errors
    logger.info("cleanup deleted %d: %s", deleted_count, deleted)
    return deleted_count, errors


def _model_types(*, include_supporting: bool) -> list[type]:
    model_types = [
        olca_schema.ProductSystem,
        olca_schema.Process,
        olca_schema.Flow,
    ]
    if include_supporting:
        model_types.extend([olca_schema.FlowProperty, olca_schema.UnitGroup])
    return model_types


def _journal_entity_targets(workspace: Path) -> list[tuple[str, str]]:
    journal = workspace / "records" / "import-operations" / "operations"
    if not journal.is_dir():
        return []
    targets: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(journal.glob("*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        for entry in report.get("entity_plan") or []:
            entity_type = str(entry.get("entity_type") or "")
            entity_id = str(entry.get("id") or "")
            key = (entity_type, entity_id)
            if entity_type and entity_id and key not in seen:
                seen.add(key)
                targets.append(key)
        for entry in report.get("entities") or []:
            if entry.get("action") != "create_or_update":
                continue
            entity_type = str(entry.get("entity_type") or "")
            entity_id = str(entry.get("id") or "")
            key = (entity_type, entity_id)
            if entity_type and entity_id and key not in seen:
                seen.add(key)
                targets.append(key)
    return targets


def _lci_entity_targets(workspace: Path) -> list[tuple[str, str]]:
    lci_root = workspace / "outputs" / "LCI"
    inventory, _errors = load_lci_inventory(lci_root)
    return [(str(item["entity_type"]), str(item["id"])) for item in inventory]


def _resolve_uuid_targets(
    client: OpenLcaClient,
    project_name: str,
    targets: list[tuple[str, str]],
    *,
    host: str | None = None,
    port: int | None = None,
) -> tuple[list[tuple[type, object]], list[dict[str, str]]]:
    resolved: list[tuple[type, object]] = []
    skipped: list[dict[str, str]] = []
    for entity_type_name, entity_id in targets:
        model_type = ENTITY_TYPES.get(entity_type_name)
        if model_type is None or not entity_id:
            continue
        try:
            existing = read_with_retry(
                f"{entity_type_name} {entity_id}",
                lambda model_type=model_type, entity_id=entity_id: client.get(
                    model_type, entity_id
                ),
                host=host,
                port=port,
            )
        except CleanupReadTimeout:
            raise
        except Exception as exc:
            skipped.append(
                {
                    "type": entity_type_name,
                    "id": entity_id,
                    "reason": f"lookup failed: {exc}",
                }
            )
            continue
        if existing is None:
            continue
        category = getattr(existing, "category", None)
        if not is_in_project_category(category, project_name):
            skipped.append(
                {
                    "type": entity_type_name,
                    "id": entity_id,
                    "name": str(getattr(existing, "name", "") or ""),
                    "category": str(category or ""),
                    "reason": "entity outside target category",
                }
            )
            continue
        resolved.append((model_type, existing))
    return resolved, skipped


def _serialize_entities(
    entities: list[tuple[type, OlcaDescriptor]],
) -> list[dict[str, str]]:
    return [
        {
            "type": model_type.__name__,
            "id": str(descriptor.id),
            "name": str(descriptor.name),
            "category": str(getattr(descriptor, "category", "") or ""),
        }
        for model_type, descriptor in entities
    ]


def run_cleanup_output(
    host: str,
    port: int,
    target_category: str,
    *,
    include_supporting: bool = False,
    confirm: bool = False,
    workspace: Path | str | None = None,
) -> dict[str, Any]:
    """Preview or delete ProductSystem, Process, and Flow under a project category."""
    project_name = target_category.strip()
    if not project_name:
        return {
            "ok": False,
            "target_category": target_category,
            "confirm": confirm,
            "entity_count": 0,
            "deleted_count": 0,
            "entities": [],
            "errors": ["target_category cannot be empty"],
        }

    model_types = _model_types(include_supporting=include_supporting)
    client = connect_ipc(
        host,
        port,
        olca_schema.ProductSystem,
    )
    try:
        entities = collect_entities(
            client, project_name, model_types, host=host, port=port
        )
        uuid_skipped: list[dict[str, str]] = []
        if workspace is not None:
            workspace_path = Path(workspace)
            uuid_targets = _lci_entity_targets(workspace_path) + _journal_entity_targets(
                workspace_path
            )
            uuid_entities, uuid_skipped = _resolve_uuid_targets(
                client, project_name, uuid_targets, host=host, port=port
            )
            known_ids = {
                (model_type.__name__, str(getattr(descriptor, "id", "")))
                for model_type, descriptor in entities
            }
            for model_type, entity in uuid_entities:
                entity_id = str(getattr(entity, "id", "") or "")
                key = (model_type.__name__, entity_id)
                if key in known_ids:
                    continue
                known_ids.add(key)
                entities.append((model_type, entity))
        serialized = _serialize_entities(entities)
        if not confirm:
            payload = {
                "ok": True,
                "target_category": project_name,
                "confirm": False,
                "entity_count": len(serialized),
                "deleted_count": 0,
                "entities": serialized,
                "errors": [],
            }
            if uuid_skipped:
                payload["skipped_uuid_cleanup"] = uuid_skipped
            return payload

        deleted_count, errors = delete_entities(
            client,
            entities,
            model_types,
            project_name=project_name,
            host=host,
            port=port,
        )
        payload = {
            "ok": not errors,
            "target_category": project_name,
            "confirm": True,
            "entity_count": len(serialized),
            "deleted_count": deleted_count,
            "entities": serialized,
            "errors": errors,
        }
        if uuid_skipped:
            payload["skipped_uuid_cleanup"] = uuid_skipped
        if errors and any(
            "timeout" in str(item).lower() or "timed out" in str(item).lower()
            for item in errors
        ):
            payload.update(
                retryable=False,
                error_kind="openlca_unresponsive",
                agent_action="stop_and_submit_failed",
            )
        return payload
    except RuntimeError as exc:
        return {
            "ok": False,
            "target_category": project_name,
            "confirm": confirm,
            "entity_count": 0,
            "deleted_count": 0,
            "entities": [],
            "errors": [str(exc)],
        }
    except Exception as exc:
        if is_transport_error(exc):
            on_ipc_transport_failure(host, port, exc, operation="cleanup_output")
            failure = {
                "ok": False,
                "target_category": project_name,
                "confirm": confirm,
                "entity_count": 0,
                "deleted_count": 0,
                "entities": [],
                "errors": [str(exc)],
                "retryable": False,
                "error_kind": "openlca_unresponsive",
                "agent_action": "stop_and_submit_failed",
            }
            return failure
        raise
    finally:
        close_ipc_client(client)
