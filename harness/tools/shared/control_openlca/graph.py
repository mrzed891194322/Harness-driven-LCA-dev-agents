from __future__ import annotations

from typing import Any

import olca_schema

from .connection import (
    build_endpoint,
    close_ipc_client,
    create_ipc_client,
)
from .entity import find_entity
from .protocols import OpenLcaClient
from .readonly import (
    category_outside_project,
    category_project_scope,
)
from .lci_inventory import (
    utc_now,
)


def model_graph_from_product_system(
    product_system: object,
    endpoint: str,
    expected_process_ids: list[str] | None = None,
    *,
    target_category: str = "",
    process_categories: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Convert an openLCA ProductSystem into a structured graph with link checks."""
    process_refs = list(getattr(product_system, "processes", None) or [])
    process_links = list(getattr(product_system, "process_links", None) or [])
    category_scope = target_category.strip()
    categories = process_categories or {}
    nodes = []
    for process in process_refs:
        process_id = getattr(process, "id", None)
        category = categories.get(str(process_id or ""))
        node = {
            "id": process_id,
            "name": getattr(process, "name", None),
        }
        if category is not None or process_id in categories:
            node["category"] = category
            node["outside_project"] = category_outside_project(category, category_scope)
            node["project_scope"] = category_project_scope(category, category_scope)
        nodes.append(node)
    node_ids = {node["id"] for node in nodes if node["id"]}
    connected_ids: set[str] = set()
    edges: list[dict[str, Any]] = []
    broken_links: list[dict[str, Any]] = []

    for index, link in enumerate(process_links, start=1):
        provider = getattr(link, "provider", None)
        flow = getattr(link, "flow", None)
        process = getattr(link, "process", None)
        provider_ref = {
            "id": getattr(provider, "id", None),
            "name": getattr(provider, "name", None),
        }
        flow_ref = {
            "id": getattr(flow, "id", None),
            "name": getattr(flow, "name", None),
        }
        process_ref = {
            "id": getattr(process, "id", None),
            "name": getattr(process, "name", None),
        }
        edges.append(
            {
                "index": index,
                "provider": provider_ref,
                "flow": flow_ref,
                "process": process_ref,
            }
        )
        reasons: list[str] = []
        if not provider_ref["id"]:
            reasons.append("missing provider")
        elif provider_ref["id"] not in node_ids:
            reasons.append("provider is not present in product-system nodes")
        else:
            connected_ids.add(provider_ref["id"])
        if not process_ref["id"]:
            reasons.append("missing receiving process")
        elif process_ref["id"] not in node_ids:
            reasons.append("receiving process is not present in product-system nodes")
        else:
            connected_ids.add(process_ref["id"])
        if not flow_ref["id"]:
            reasons.append("missing flow")
        if reasons:
            broken_links.append({"edge_index": index, "reasons": reasons})

    disconnected_nodes = [
        node for node in nodes if len(nodes) > 1 and node["id"] not in connected_ids
    ]
    expected_ids = sorted(
        {
            value.strip()
            for value in (expected_process_ids or [])
            if isinstance(value, str) and value.strip()
        }
    )
    missing_expected_nodes = [
        process_id for process_id in expected_ids if process_id not in node_ids
    ]
    if not nodes:
        status = "failed"
        error = (
            "ProductSystem has no process nodes; automatic processLinks may be missing"
        )
    elif broken_links or disconnected_nodes or missing_expected_nodes:
        status = "broken"
        error = None
    else:
        status = "success"
        error = None
    return {
        "schema": "whole-lca/model-graph",
        "version": "1.1",
        "status": status,
        "endpoint": endpoint,
        "product_system": {
            "id": getattr(product_system, "id", None),
            "name": getattr(product_system, "name", None),
        },
        "nodes": nodes,
        "edges": edges,
        "broken_links": broken_links,
        "disconnected_nodes": disconnected_nodes,
        "expected_process_ids": expected_ids,
        "missing_expected_nodes": missing_expected_nodes,
        "timestamp": utc_now(),
        "error": error,
    }


def get_model_graph(
    host: str,
    port: int,
    product_system: str,
    client: OpenLcaClient | None = None,
    expected_process_ids: list[str] | None = None,
    target_category: str = "",
) -> dict[str, Any]:
    endpoint = build_endpoint(host, port)
    owns_client = client is None
    ipc_client = client or create_ipc_client(host, port)
    try:
        process_categories: dict[str, str | None] = {}
        if hasattr(ipc_client, "get_descriptors"):
            for descriptor in list(ipc_client.get_descriptors(olca_schema.Process) or []):
                descriptor_id = getattr(descriptor, "id", None)
                if isinstance(descriptor_id, str) and descriptor_id:
                    process_categories[descriptor_id] = getattr(
                        descriptor, "category", None
                    )
        system = find_entity(ipc_client, olca_schema.ProductSystem, product_system)
        if system is None:
            result = {
                "schema": "whole-lca/model-graph",
                "version": "1.1",
                "status": "failed",
                "endpoint": endpoint,
                "product_system": {"id": None, "name": product_system},
                "nodes": [],
                "edges": [],
                "broken_links": [{"reason": "Product System was not found"}],
                "disconnected_nodes": [],
                "expected_process_ids": expected_process_ids or [],
                "missing_expected_nodes": expected_process_ids or [],
                "timestamp": utc_now(),
                "error": f"Product System not found: {product_system}",
            }
            return result
        result = model_graph_from_product_system(
            system,
            endpoint,
            expected_process_ids=expected_process_ids,
            target_category=target_category,
            process_categories=process_categories,
        )
        result["target_category"] = target_category.strip() or None
        return result
    finally:
        if owns_client:
            close_ipc_client(ipc_client)
