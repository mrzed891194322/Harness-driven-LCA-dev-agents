from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import olca_schema

from .connection import build_endpoint, create_ipc_client
from .entity import find_entity


ENTITY_IMPORT_ORDER: tuple[str, ...] = (
    "UnitGroup",
    "FlowProperty",
    "Flow",
    "Process",
    "ProductSystem",
)
ENTITY_DELETE_ORDER: tuple[str, ...] = tuple(reversed(ENTITY_IMPORT_ORDER))
ENTITY_TYPES: dict[str, type] = {
    name: getattr(olca_schema, name) for name in ENTITY_IMPORT_ORDER
}
ALLOCATION_TYPES: dict[str, Any] = {
    "physical": olca_schema.AllocationType.PHYSICAL_ALLOCATION,
    "economic": olca_schema.AllocationType.ECONOMIC_ALLOCATION,
    "causal": olca_schema.AllocationType.CAUSAL_ALLOCATION,
    "none": olca_schema.AllocationType.NO_ALLOCATION,
    "default": olca_schema.AllocationType.USE_DEFAULT_ALLOCATION,
}


def utc_now() -> str:
    """Return an RFC 3339 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_lci_inventory(json_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read importable LCI JSON files without accessing openLCA."""
    root = json_dir.resolve()
    if not root.is_dir():
        return [], [f"LCI directory does not exist: {root}"]

    subdirs = ("flows", "processes", "product_systems")
    has_subdirs = any((root / subdir).is_dir() for subdir in subdirs)
    paths: list[Path] = []
    if has_subdirs:
        for subdir in subdirs:
            paths.extend(sorted((root / subdir).glob("*.json")))
        paths.extend(sorted(path for path in root.glob("*.json") if path.is_file()))
    else:
        paths.extend(sorted(root.glob("*.json")))

    if not paths:
        return [], [f"No JSON files found in LCI directory: {root}"]

    inventory: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    for path in paths:
        relative_path = path.relative_to(root).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{relative_path}: invalid JSON: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{relative_path}: JSON root must be an object")
            continue

        entity_type = data.get("@type")
        entity_id = data.get("@id")
        entity_name = data.get("name")
        if entity_type not in ENTITY_TYPES:
            errors.append(f"{relative_path}: unsupported @type {entity_type!r}")
            continue
        if not isinstance(entity_id, str) or not entity_id:
            errors.append(f"{relative_path}: missing non-empty @id")
            continue
        if entity_id in seen_ids:
            errors.append(f"{relative_path}: duplicate @id {entity_id}")
            continue
        if not isinstance(entity_name, str) or not entity_name:
            errors.append(f"{relative_path}: missing non-empty name")
            continue
        try:
            ENTITY_TYPES[entity_type].from_dict(data)
        except Exception as exc:
            errors.append(f"{relative_path}: cannot deserialize {entity_type}: {exc}")
            continue

        seen_ids.add(entity_id)
        inventory.append(
            {
                "path": relative_path,
                "absolute_path": path,
                "sha256": sha256_file(path),
                "entity_type": entity_type,
                "id": entity_id,
                "name": entity_name,
                "data": data,
            }
        )

    order = {name: index for index, name in enumerate(ENTITY_IMPORT_ORDER)}
    inventory.sort(key=lambda item: (order[item["entity_type"]], item["path"]))
    return inventory, errors


def _descriptor_record(entity_type: str, descriptor: object) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "id": getattr(descriptor, "id", None),
        "name": getattr(descriptor, "name", None),
        "category": getattr(descriptor, "category", None),
    }


def _database_snapshot(
    client: object,
    target_category: str,
) -> tuple[list[dict[str, Any]], list[tuple[str, object]]]:
    all_records: list[dict[str, Any]] = []
    target_descriptors: list[tuple[str, object]] = []
    for entity_type in ENTITY_DELETE_ORDER:
        model_type = ENTITY_TYPES[entity_type]
        descriptors = list(client.get_descriptors(model_type) or [])
        for descriptor in descriptors:
            record = _descriptor_record(entity_type, descriptor)
            all_records.append(record)
            category = record["category"]
            if isinstance(category, str) and (
                category == target_category
                or category.startswith(f"{target_category}/")
            ):
                target_descriptors.append((entity_type, descriptor))
    all_records.sort(
        key=lambda item: (
            item["entity_type"],
            str(item["id"] or ""),
            str(item["category"] or ""),
        )
    )
    return all_records, target_descriptors


def _active_database_label(endpoint: str, database_name: str | None) -> tuple[str, str]:
    explicit = (database_name or "").strip()
    if explicit:
        return explicit, "argument"
    configured = os.getenv("OPENLCA_DATABASE_NAME", "").strip()
    if configured:
        return configured, "OPENLCA_DATABASE_NAME"
    return f"active-database@{endpoint}", "endpoint-fallback"


def _inspect_import(
    host: str,
    port: int,
    lci_dir: str | Path,
    target_category: str,
    database_name: str | None = None,
    client: object | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[tuple[str, object]]]:
    endpoint = build_endpoint(host, port)
    category = target_category.strip()
    if not category:
        raise ValueError("target_category must not be empty")
    root = Path(lci_dir).resolve()
    inventory, errors = load_lci_inventory(root)
    active_database, identity_source = _active_database_label(endpoint, database_name)

    if errors:
        return (
            {
                "schema": "whole-lca/import-preflight",
                "version": "1.0",
                "ok": False,
                "status": "invalid_lci",
                "endpoint": endpoint,
                "active_database": active_database,
                "database_identity_source": identity_source,
                "database_fingerprint": None,
                "lci_dir": str(root),
                "target_category": category,
                "planned_entities": [],
                "overwrite_delete_scope": [],
                "counts": {"planned": 0, "overwrite_or_delete": 0},
                "errors": errors,
                "preflight_hash": None,
                "timestamp": utc_now(),
            },
            inventory,
            [],
        )

    ipc_client = client or create_ipc_client(host, port)
    try:
        database_records, target_descriptors = _database_snapshot(ipc_client, category)
    except Exception as exc:
        raise RuntimeError(f"Failed to inspect active openLCA database at {endpoint}: {exc}") from exc

    database_fingerprint = stable_hash(database_records)
    planned_entities = [
        {
            "path": item["path"],
            "sha256": item["sha256"],
            "entity_type": item["entity_type"],
            "id": item["id"],
            "name": item["name"],
            "action": "create_or_update",
        }
        for item in inventory
    ]
    overwrite_scope = [
        {**_descriptor_record(entity_type, descriptor), "action": "delete"}
        for entity_type, descriptor in target_descriptors
    ]
    overwrite_scope.sort(
        key=lambda item: (item["entity_type"], str(item["id"] or ""))
    )
    hash_payload = {
        "version": "1.0",
        "endpoint": endpoint,
        "active_database": active_database,
        "database_fingerprint": database_fingerprint,
        "target_category": category,
        "planned_entities": planned_entities,
        "overwrite_delete_scope": overwrite_scope,
    }
    preflight_hash = stable_hash(hash_payload)
    return (
        {
            "schema": "whole-lca/import-preflight",
            "version": "1.0",
            "ok": True,
            "status": "ready",
            "endpoint": endpoint,
            "active_database": active_database,
            "database_identity_source": identity_source,
            "database_fingerprint": database_fingerprint,
            "lci_dir": str(root),
            "target_category": category,
            "planned_entities": planned_entities,
            "overwrite_delete_scope": overwrite_scope,
            "counts": {
                "planned": len(planned_entities),
                "overwrite_or_delete": len(overwrite_scope),
            },
            "errors": [],
            "preflight_hash": preflight_hash,
            "timestamp": utc_now(),
        },
        inventory,
        target_descriptors,
    )


def preflight_import_lci(
    host: str,
    port: int,
    lci_dir: str | Path,
    target_category: str,
    database_name: str | None = None,
    client: object | None = None,
) -> dict[str, Any]:
    """Inspect an LCI import without calling openLCA put or delete operations."""
    preflight, _, _ = _inspect_import(
        host=host,
        port=port,
        lci_dir=lci_dir,
        target_category=target_category,
        database_name=database_name,
        client=client,
    )
    return preflight


def _deserialize_entity(item: dict[str, Any], target_category: str) -> object:
    entity = ENTITY_TYPES[item["entity_type"]].from_dict(item["data"])
    if hasattr(entity, "category"):
        entity.category = target_category
    return entity


def _execute_import(
    client: object,
    inventory: list[dict[str, Any]],
    target_descriptors: list[tuple[str, object]],
    target_category: str,
    emit: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], int, int, int, list[str]]:
    records: list[dict[str, Any]] = []
    imported = 0
    failed = 0
    deleted = 0
    errors: list[str] = []
    output = emit or (lambda _message: None)

    for entity_type in ENTITY_DELETE_ORDER:
        for current_type, descriptor in target_descriptors:
            if current_type != entity_type:
                continue
            entity_id = getattr(descriptor, "id", None)
            entity_name = getattr(descriptor, "name", None)
            try:
                reference = descriptor.to_ref()
                client.delete(reference)
                deleted += 1
                output(f"  [已删除] {entity_type}: {entity_name} (UUID: {entity_id})")
                records.append(
                    {
                        "path": "openlca://active-database",
                        "entity_type": entity_type,
                        "id": entity_id,
                        "name": entity_name,
                        "action": "delete",
                        "status": "success",
                        "error": None,
                    }
                )
            except Exception as exc:
                failed += 1
                message = f"delete {entity_type} {entity_id}: {exc}"
                errors.append(message)
                output(f"  [错误] {message}")
                records.append(
                    {
                        "path": "openlca://active-database",
                        "entity_type": entity_type,
                        "id": entity_id,
                        "name": entity_name,
                        "action": "delete",
                        "status": "failed",
                        "error": str(exc),
                    }
                )

    for item in inventory:
        output(f"正在处理文件: {item['path']}...")
        try:
            entity = _deserialize_entity(item, target_category)
            reference = client.put(entity)
            if reference is None:
                raise RuntimeError("IPC Server did not return an entity reference")
            imported += 1
            returned_id = getattr(reference, "id", None) or item["id"]
            output(
                f"[成功] 成功导入 {item['entity_type']}: "
                f"'{item['name']}' (ID: {returned_id})"
            )
            records.append(
                {
                    "path": item["path"],
                    "entity_type": item["entity_type"],
                    "id": returned_id,
                    "name": item["name"],
                    "action": "create_or_update",
                    "status": "success",
                    "error": None,
                }
            )
        except Exception as exc:
            failed += 1
            message = f"import {item['path']}: {exc}"
            errors.append(message)
            output(f"[错误] {message}")
            records.append(
                {
                    "path": item["path"],
                    "entity_type": item["entity_type"],
                    "id": item["id"],
                    "name": item["name"],
                    "action": "create_or_update",
                    "status": "failed",
                    "error": str(exc),
                }
            )
    return records, imported, failed, deleted, errors


def _rejected_import_report(
    endpoint: str,
    active_database: str,
    target_category: str,
    preflight_hash: str,
    started_at: str,
    started_clock: float,
    errors: list[str],
) -> dict[str, Any]:
    ended_at = utc_now()
    return {
        "schema": "whole-lca/import-report",
        "version": "1.0",
        "operation_id": str(uuid.uuid4()),
        "status": "rejected",
        "endpoint": endpoint,
        "active_database": active_database,
        "target_category": target_category,
        "preflight_hash": preflight_hash,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": max(0, round((time.monotonic() - started_clock) * 1000)),
        "success_count": 0,
        "failed_count": 0,
        "deleted_count": 0,
        "entities": [],
        "errors": errors,
    }


def import_lci(
    host: str,
    port: int,
    lci_dir: str | Path,
    target_category: str,
    preflight_hash: str,
    user_confirmed: bool,
    database_name: str | None = None,
    client: object | None = None,
) -> dict[str, Any]:
    """Import LCI only after an unchanged preflight has explicit confirmation."""
    if (
        not isinstance(preflight_hash, str)
        or len(preflight_hash) != 64
        or any(character not in "0123456789abcdef" for character in preflight_hash)
    ):
        raise ValueError("preflight_hash must be a lowercase 64-character SHA-256")
    started_at = utc_now()
    started_clock = time.monotonic()
    endpoint = build_endpoint(host, port)
    active_database, _ = _active_database_label(endpoint, database_name)
    if not user_confirmed:
        return _rejected_import_report(
            endpoint,
            active_database,
            target_category,
            preflight_hash,
            started_at,
            started_clock,
            ["Import rejected: user_confirmed must be true."],
        )

    ipc_client = client or create_ipc_client(host, port)
    current, inventory, target_descriptors = _inspect_import(
        host=host,
        port=port,
        lci_dir=lci_dir,
        target_category=target_category,
        database_name=database_name,
        client=ipc_client,
    )
    if not current["ok"]:
        return _rejected_import_report(
            endpoint,
            active_database,
            target_category,
            preflight_hash,
            started_at,
            started_clock,
            ["Import rejected: current preflight is not ready.", *current["errors"]],
        )
    if current["preflight_hash"] != preflight_hash:
        return _rejected_import_report(
            endpoint,
            current["active_database"],
            target_category,
            preflight_hash,
            started_at,
            started_clock,
            [
                "Import rejected: preflight hash mismatch; LCI, database, category, "
                "or overwrite scope changed.",
                f"current_preflight_hash={current['preflight_hash']}",
            ],
        )

    records, imported, failed, deleted, errors = _execute_import(
        client=ipc_client,
        inventory=inventory,
        target_descriptors=target_descriptors,
        target_category=target_category,
    )
    status = "success" if failed == 0 and imported == len(inventory) else "partial_failure"
    if imported == 0 and failed:
        status = "failed"
    return {
        "schema": "whole-lca/import-report",
        "version": "1.0",
        "operation_id": str(uuid.uuid4()),
        "status": status,
        "endpoint": endpoint,
        "active_database": current["active_database"],
        "target_category": target_category,
        "preflight_hash": preflight_hash,
        "started_at": started_at,
        "ended_at": utc_now(),
        "duration_ms": max(0, round((time.monotonic() - started_clock) * 1000)),
        "success_count": imported,
        "failed_count": failed,
        "deleted_count": deleted,
        "entities": records,
        "errors": errors,
    }


def legacy_import_lci(
    client: object,
    json_dir: Path,
    target_category: str,
    emit: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run the historical CLI import behavior through the shared service."""
    inventory, errors = load_lci_inventory(json_dir)
    for error in errors:
        prefix = "[警告]" if error.startswith("No JSON files") else "[错误]"
        emit(f"{prefix} {error}")
    if not inventory:
        return {"success_count": 0, "failed_count": len(errors), "errors": errors}
    target_descriptors = _legacy_target_descriptors(client, target_category, emit)
    if target_descriptors:
        emit(
            f"检测到分类 '{target_category}' 下已存在 {len(target_descriptors)} "
            "个实体，正在执行清空以避免冲突..."
        )
    else:
        emit(f"未在 openLCA 中找到分类 '{target_category}' 下的现有内容。无需清空。")
    emit(f"正在遍历并导入 {len(inventory)} 个 JSON 文件。")
    records, imported, failed, deleted, import_errors = _execute_import(
        client=client,
        inventory=inventory,
        target_descriptors=target_descriptors,
        target_category=target_category,
        emit=emit,
    )
    return {
        "success_count": imported,
        "failed_count": failed + len(errors),
        "deleted_count": deleted,
        "entities": records,
        "errors": [*errors, *import_errors],
    }


def _legacy_target_descriptors(
    client: object,
    target_category: str,
    emit: Callable[[str], None],
) -> list[tuple[str, object]]:
    descriptors_in_scope: list[tuple[str, object]] = []
    for entity_type in ENTITY_DELETE_ORDER:
        try:
            descriptors = list(client.get_descriptors(ENTITY_TYPES[entity_type]) or [])
        except Exception as exc:
            emit(f"[警告] 获取 {entity_type} 描述符失败: {exc}")
            continue
        for descriptor in descriptors:
            category = getattr(descriptor, "category", None)
            if isinstance(category, str) and (
                category == target_category
                or category.startswith(f"{target_category}/")
            ):
                descriptors_in_scope.append((entity_type, descriptor))
    return descriptors_in_scope


def legacy_clear_category(
    client: object,
    target_category: str,
    emit: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Clear a category with the historical dependency-aware deletion order."""
    target_descriptors = _legacy_target_descriptors(client, target_category, emit)
    records, _, failed, deleted, errors = _execute_import(
        client=client,
        inventory=[],
        target_descriptors=target_descriptors,
        target_category=target_category,
        emit=emit,
    )
    return {
        "deleted_count": deleted,
        "failed_count": failed,
        "entities": records,
        "errors": errors,
    }


def model_graph_from_product_system(
    product_system: object,
    endpoint: str,
) -> dict[str, Any]:
    """Convert an openLCA ProductSystem into a structured graph with link checks."""
    process_refs = list(getattr(product_system, "processes", None) or [])
    process_links = list(getattr(product_system, "process_links", None) or [])
    nodes = [
        {"id": getattr(process, "id", None), "name": getattr(process, "name", None)}
        for process in process_refs
    ]
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
    status = "success" if not broken_links else "broken"
    return {
        "schema": "whole-lca/model-graph",
        "version": "1.0",
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
        "timestamp": utc_now(),
        "error": None,
    }


def get_model_graph(
    host: str,
    port: int,
    product_system: str,
    client: object | None = None,
) -> dict[str, Any]:
    endpoint = build_endpoint(host, port)
    ipc_client = client or create_ipc_client(host, port)
    system = find_entity(ipc_client, olca_schema.ProductSystem, product_system)
    if system is None:
        return {
            "schema": "whole-lca/model-graph",
            "version": "1.0",
            "status": "failed",
            "endpoint": endpoint,
            "product_system": {"id": None, "name": product_system},
            "nodes": [],
            "edges": [],
            "broken_links": [{"reason": "Product System was not found"}],
            "disconnected_nodes": [],
            "timestamp": utc_now(),
            "error": f"Product System not found: {product_system}",
        }
    system_id = getattr(system, "id", None)
    if system_id:
        loaded = ipc_client.get(olca_schema.ProductSystem, system_id)
        if loaded is not None:
            system = loaded
    return model_graph_from_product_system(system, endpoint)


def build_calculation_setup(
    target: object,
    method: object | None,
    amount: float,
    allocation: str | None,
    regionalized: bool,
    costs: bool,
    parameters: dict[str, float] | None,
) -> olca_schema.CalculationSetup:
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("amount must be a positive number")
    allocation_key = allocation.casefold() if allocation else None
    if allocation_key and allocation_key not in ALLOCATION_TYPES:
        raise ValueError(
            "allocation must be one of physical, economic, causal, none, default"
        )
    parameter_redefs: list[olca_schema.ParameterRedef] = []
    for name, value in (parameters or {}).items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("parameter names must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"parameter {name!r} must have a numeric value")
        parameter_redefs.append(
            olca_schema.ParameterRedef(name=name.strip(), value=float(value))
        )

    setup = olca_schema.CalculationSetup()
    setup.target = olca_schema.as_ref(target)
    setup.amount = float(amount)
    if method is not None:
        setup.impact_method = olca_schema.as_ref(method)
    if allocation_key:
        setup.allocation = ALLOCATION_TYPES[allocation_key]
    if regionalized:
        setup.with_regionalization = True
    if costs:
        setup.with_costs = True
    if parameter_redefs:
        setup.parameters = parameter_redefs
    return setup


def calculate_handle(client: object, setup: olca_schema.CalculationSetup) -> object:
    """Start a calculation and wait for readiness; callers own disposal."""
    result = client.calculate(setup)
    if hasattr(result, "wait_until_ready"):
        result.wait_until_ready()
    return result


def calculate_product_system(
    host: str,
    port: int,
    product_system: str,
    impact_method: str,
    amount: float = 1.0,
    allocation: str | None = None,
    regionalized: bool = False,
    costs: bool = False,
    parameters: dict[str, float] | None = None,
    client: object | None = None,
) -> dict[str, Any]:
    endpoint = build_endpoint(host, port)
    ipc_client = client or create_ipc_client(host, port)
    system = find_entity(ipc_client, olca_schema.ProductSystem, product_system)
    method = find_entity(ipc_client, olca_schema.ImpactMethod, impact_method)
    started_at = utc_now()
    base = {
        "schema": "whole-lca/raw-lcia-results",
        "version": "1.0",
        "endpoint": endpoint,
        "product_system": {
            "id": getattr(system, "id", None),
            "name": getattr(system, "name", None) or product_system,
        },
        "impact_method": {
            "id": getattr(method, "id", None),
            "name": getattr(method, "name", None) or impact_method,
        },
        "calculation_setup": {
            "amount": amount,
            "allocation": allocation,
            "regionalized": regionalized,
            "costs": costs,
            "parameters": parameters or {},
        },
        "impact_categories": [],
        "resource_released": False,
        "started_at": started_at,
        "ended_at": started_at,
        "error": None,
    }
    if system is None or method is None:
        missing = "Product System" if system is None else "Impact Method"
        return {**base, "status": "failed", "ended_at": utc_now(), "error": f"{missing} not found"}

    result = None
    status = "failed"
    error: str | None = None
    impacts: list[dict[str, Any]] = []
    released = False
    try:
        setup = build_calculation_setup(
            target=system,
            method=method,
            amount=amount,
            allocation=allocation,
            regionalized=regionalized,
            costs=costs,
            parameters=parameters,
        )
        result = calculate_handle(ipc_client, setup)
        for impact in list(result.get_total_impacts() or []):
            category = getattr(impact, "impact_category", None)
            impacts.append(
                {
                    "name": getattr(category, "name", None) or "Unknown",
                    "id": getattr(category, "id", None) or "Unknown",
                    "amount": float(getattr(impact, "amount", 0.0) or 0.0),
                    "unit": getattr(category, "ref_unit", None) or "",
                }
            )
        status = "success" if impacts else "empty"
    except Exception as exc:
        error = str(exc)
        status = "failed"
    finally:
        if result is not None:
            try:
                result.dispose()
                released = True
            except Exception as exc:
                error = f"{error}; dispose failed: {exc}" if error else f"dispose failed: {exc}"
                status = "failed"

    return {
        **base,
        "status": status,
        "impact_categories": impacts,
        "resource_released": released,
        "ended_at": utc_now(),
        "error": error,
    }
