from __future__ import annotations

from typing import Any

import olca_schema

from .connection import build_endpoint, create_ipc_client, probe_ipc


ENTITY_TYPES: dict[str, type] = {
    "Process": olca_schema.Process,
    "Flow": olca_schema.Flow,
    "ProductSystem": olca_schema.ProductSystem,
    "ImpactMethod": olca_schema.ImpactMethod,
    "FlowProperty": olca_schema.FlowProperty,
    "UnitGroup": olca_schema.UnitGroup,
    "Actor": olca_schema.Actor,
    "Source": olca_schema.Source,
    "Project": olca_schema.Project,
    "Location": olca_schema.Location,
    "Currency": olca_schema.Currency,
    "SocialIndicator": olca_schema.SocialIndicator,
}

DEFAULT_QUERY_LIMIT = 50
MAX_QUERY_LIMIT = 200


def health_check(host: str, port: int) -> dict[str, Any]:
    """Return a structured diagnostic result for an openLCA IPC endpoint."""
    endpoint = build_endpoint(host, port)
    try:
        probe_ipc(host, port, olca_schema.Process)
    except Exception as exc:
        return {
            "ok": False,
            "endpoint": endpoint,
            "error": str(exc),
            "error_type": type(exc).__name__,
            "diagnostics": [
                "Confirm that the openLCA desktop application is running.",
                f"Confirm that Tools > Developer Tools > IPC Server is enabled on port {port}.",
                "Confirm that the endpoint is reachable from the MCP server process.",
            ],
        }
    return {
        "ok": True,
        "endpoint": endpoint,
        "message": "openLCA IPC Server is reachable and descriptor queries succeed.",
    }


def query_descriptors(
    host: str,
    port: int,
    entity_type: str,
    search: str = "",
    limit: int = DEFAULT_QUERY_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    """Query and paginate descriptors from the active openLCA database."""
    model_type = _validate_query(entity_type, search, limit, offset)
    endpoint = build_endpoint(host, port)
    try:
        client = create_ipc_client(host, port)
        descriptors = list(client.get_descriptors(model_type) or [])
    except Exception as exc:
        raise RuntimeError(
            f"Failed to query {entity_type} descriptors from {endpoint}: {exc}"
        ) from exc

    search_text = search.strip()
    search_key = search_text.casefold()
    matches = [
        descriptor
        for descriptor in descriptors
        if search_key in str(getattr(descriptor, "name", "") or "").casefold()
    ]
    page = matches[offset : offset + limit]
    items = [_descriptor_to_dict(entity_type, descriptor) for descriptor in page]
    next_offset = offset + len(items)
    has_more = next_offset < len(matches)
    return {
        "ok": True,
        "endpoint": endpoint,
        "entity_type": entity_type,
        "search": search_text,
        "total_descriptors": len(descriptors),
        "total_matches": len(matches),
        "offset": offset,
        "limit": limit,
        "returned": len(items),
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
        "items": items,
    }


def _validate_query(entity_type: str, search: str, limit: int, offset: int) -> type:
    if entity_type not in ENTITY_TYPES:
        available = ", ".join(ENTITY_TYPES)
        raise ValueError(f"Unsupported entity_type {entity_type!r}; available: {available}")
    if not isinstance(search, str):
        raise ValueError("search must be a string")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_QUERY_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_QUERY_LIMIT}")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    return ENTITY_TYPES[entity_type]


def _descriptor_to_dict(entity_type: str, descriptor: object) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "id": getattr(descriptor, "id", None),
        "name": getattr(descriptor, "name", None),
        "description": getattr(descriptor, "description", None),
        "category": getattr(descriptor, "category", None),
        "ref_unit": getattr(descriptor, "ref_unit", None),
    }
