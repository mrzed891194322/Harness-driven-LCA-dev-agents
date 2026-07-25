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


def get_process_details(
    host: str,
    port: int,
    process_id: str,
) -> dict[str, Any]:
    """Return the location and quantitative reference for one Process UUID."""
    _validate_identifier("process_id", process_id)
    endpoint = build_endpoint(host, port)
    try:
        client = create_ipc_client(host, port)
        process = client.get(olca_schema.Process, process_id)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read Process {process_id} from {endpoint}: {exc}"
        ) from exc

    return {
        "ok": True,
        "endpoint": endpoint,
        "process_id": process_id,
        "found": process is not None,
        "process": _process_to_dict(process) if process is not None else None,
    }


def get_flow_providers(
    host: str,
    port: int,
    flow_id: str,
    location: str = "",
    limit: int = DEFAULT_QUERY_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    """Return compact provider references for one exact Flow UUID."""
    _validate_identifier("flow_id", flow_id)
    _validate_pagination(limit, offset)
    if not isinstance(location, str):
        raise ValueError("location must be a string")

    endpoint = build_endpoint(host, port)
    try:
        client = create_ipc_client(host, port)
        flow = client.get(olca_schema.Flow, flow_id)
        tech_flows = list(client.get_providers(flow) or []) if flow is not None else []
    except Exception as exc:
        raise RuntimeError(
            f"Failed to query providers for Flow {flow_id} from {endpoint}: {exc}"
        ) from exc

    location_text = location.strip()
    location_key = location_text.casefold()
    providers = sorted(
        (
            _tech_flow_to_dict(tech_flow)
            for tech_flow in tech_flows
            if getattr(tech_flow, "provider", None) is not None
        ),
        key=lambda item: (
            str(item["provider_name"] or "").casefold(),
            str(item["provider_id"] or ""),
        ),
    )
    matches = [
        provider
        for provider in providers
        if not location_key
        or location_key in str(provider["provider_location"] or "").casefold()
    ]
    page = matches[offset : offset + limit]
    next_offset = offset + len(page)
    has_more = next_offset < len(matches)
    return {
        "ok": True,
        "endpoint": endpoint,
        "flow_id": flow_id,
        "flow_found": flow is not None,
        "location": location_text,
        "total_providers": len(providers),
        "total_matches": len(matches),
        "offset": offset,
        "limit": limit,
        "returned": len(page),
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
        "items": page,
    }


def _validate_query(entity_type: str, search: str, limit: int, offset: int) -> type:
    if entity_type not in ENTITY_TYPES:
        available = ", ".join(ENTITY_TYPES)
        raise ValueError(f"Unsupported entity_type {entity_type!r}; available: {available}")
    if not isinstance(search, str):
        raise ValueError("search must be a string")
    _validate_pagination(limit, offset)
    return ENTITY_TYPES[entity_type]


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _validate_pagination(limit: int, offset: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_QUERY_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_QUERY_LIMIT}")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")


def _descriptor_to_dict(entity_type: str, descriptor: object) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "id": getattr(descriptor, "id", None),
        "name": getattr(descriptor, "name", None),
        "description": getattr(descriptor, "description", None),
        "category": getattr(descriptor, "category", None),
        "location": getattr(descriptor, "location", None),
        "ref_unit": getattr(descriptor, "ref_unit", None),
    }


def _tech_flow_to_dict(tech_flow: object) -> dict[str, Any]:
    provider = getattr(tech_flow, "provider", None)
    flow = getattr(tech_flow, "flow", None)
    return {
        "provider_id": getattr(provider, "id", None),
        "provider_name": getattr(provider, "name", None),
        "provider_category": getattr(provider, "category", None),
        "provider_location": getattr(provider, "location", None),
        "flow_id": getattr(flow, "id", None),
        "flow_name": getattr(flow, "name", None),
        "flow_ref_unit": getattr(flow, "ref_unit", None),
    }


def _process_to_dict(process: object) -> dict[str, Any]:
    quantitative_references = []
    for exchange in list(getattr(process, "exchanges", None) or []):
        if getattr(exchange, "is_quantitative_reference", None) is not True:
            continue
        quantitative_references.append(
            {
                "flow": _reference_to_dict(getattr(exchange, "flow", None)),
                "amount": getattr(exchange, "amount", None),
                "unit": _reference_to_dict(getattr(exchange, "unit", None)),
                "flow_property": _reference_to_dict(
                    getattr(exchange, "flow_property", None)
                ),
                "is_input": getattr(exchange, "is_input", None),
            }
        )
    return {
        "id": getattr(process, "id", None),
        "name": getattr(process, "name", None),
        "category": getattr(process, "category", None),
        "location": _reference_to_dict(getattr(process, "location", None)),
        "quantitative_references": quantitative_references,
    }


def _reference_to_dict(reference: object | None) -> dict[str, Any] | None:
    if reference is None:
        return None
    return {
        "id": getattr(reference, "id", None),
        "name": getattr(reference, "name", None),
        "category": getattr(reference, "category", None),
        "location": getattr(reference, "location", None),
        "ref_unit": getattr(reference, "ref_unit", None),
    }
