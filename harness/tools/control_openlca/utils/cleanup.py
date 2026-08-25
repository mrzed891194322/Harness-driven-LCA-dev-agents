"""Shared openLCA project-category cleanup for MCP and offline tests."""

from __future__ import annotations

from typing import Any

import olca_schema

from harness.tools.control_openlca.utils.connection import (
    LONG_REQUEST_TIMEOUT,
    close_ipc_client,
    connect_ipc,
)


def is_in_project_category(category: str | None, project_name: str) -> bool:
    if not category:
        return False
    return category == project_name or category.startswith(project_name + "/")


def collect_entities(
    client,
    project_name: str,
    model_types: list[type],
) -> list[tuple[type, object]]:
    entities: list[tuple[type, object]] = []
    for model_type in model_types:
        try:
            descriptors = client.get_descriptors(model_type)
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
    client,
    entities: list[tuple[type, object]],
    model_types: list[type],
) -> tuple[int, list[str]]:
    deleted_count = 0
    errors: list[str] = []
    for model_type in model_types:
        current = [item for item in entities if item[0] == model_type]
        for _, descriptor in current:
            try:
                client.delete(descriptor.to_ref())
                deleted_count += 1
            except Exception as exc:
                errors.append(
                    f"Failed to delete {descriptor.name} ({descriptor.id}): {exc}"
                )
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


def _serialize_entities(entities: list[tuple[type, object]]) -> list[dict[str, str]]:
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
        timeout=LONG_REQUEST_TIMEOUT,
    )
    try:
        entities = collect_entities(client, project_name, model_types)
        serialized = _serialize_entities(entities)
        if not confirm:
            return {
                "ok": True,
                "target_category": project_name,
                "confirm": False,
                "entity_count": len(serialized),
                "deleted_count": 0,
                "entities": serialized,
                "errors": [],
            }

        deleted_count, errors = delete_entities(client, entities, model_types)
        return {
            "ok": not errors,
            "target_category": project_name,
            "confirm": True,
            "entity_count": len(serialized),
            "deleted_count": deleted_count,
            "entities": serialized,
            "errors": errors,
        }
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
    finally:
        close_ipc_client(client)
