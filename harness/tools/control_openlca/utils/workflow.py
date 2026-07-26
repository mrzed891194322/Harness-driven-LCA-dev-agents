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

from .connection import (
    LONG_REQUEST_TIMEOUT,
    build_endpoint,
    close_ipc_client,
    create_ipc_client,
    is_transport_error,
)
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
JSON_LD_CONTEXT = "http://greendelta.github.io/olca-schema/context.jsonld"
LCI_ENTITY_DIRECTORIES: dict[str, str] = {
    "flows": "Flow",
    "processes": "Process",
    "product_systems": "ProductSystem",
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

    paths: list[Path] = []
    errors: list[str] = []
    for subdir in LCI_ENTITY_DIRECTORIES:
        directory = root / subdir
        if directory.is_dir():
            paths.extend(sorted(directory.glob("*.json")))

    allowed_paths = {path.resolve() for path in paths}
    for path in sorted(root.rglob("*.json")):
        if path.resolve() not in allowed_paths:
            errors.append(
                f"{path.relative_to(root).as_posix()}: JSON files are only allowed "
                "directly under flows/, processes/, or product_systems/"
            )

    if not paths:
        errors.append(f"No entity JSON files found in LCI directory: {root}")
        return [], errors

    inventory: list[dict[str, Any]] = []
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
        context = data.get("@context")
        expected_type = LCI_ENTITY_DIRECTORIES[path.parent.name]
        if context != JSON_LD_CONTEXT:
            errors.append(
                f"{relative_path}: @context must be {JSON_LD_CONTEXT!r}"
            )
            continue
        if entity_type != expected_type:
            errors.append(
                f"{relative_path}: expected @type {expected_type!r} for "
                f"{path.parent.name}/, got {entity_type!r}"
            )
            continue
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


def validate_lci_directory(json_dir: Path) -> dict[str, Any]:
    """Return a deterministic, offline Stage 03/04 LCI validation result."""
    inventory, errors = load_lci_inventory(json_dir)
    counts = {
        entity_type: sum(
            1 for item in inventory if item["entity_type"] == entity_type
        )
        for entity_type in LCI_ENTITY_DIRECTORIES.values()
    }
    required_missing = [
        entity_type for entity_type, count in counts.items() if count == 0
    ]
    for entity_type in required_missing:
        errors.append(f"LCI inventory requires at least one {entity_type} entity")
    errors.extend(_lci_semantic_errors(inventory))
    mapping_path = json_dir.resolve() / "human_readable_mapping.md"
    if not mapping_path.is_file():
        errors.append(
            "LCI inventory requires human_readable_mapping.md at the LCI root"
        )
    return {
        "schema": "whole-lca/lci-validation",
        "version": "1.0",
        "ok": not errors,
        "counts": counts,
        "entities": [
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "entity_type": item["entity_type"],
                "id": item["id"],
                "name": item["name"],
            }
            for item in inventory
        ],
        "errors": errors,
    }


def _lci_semantic_errors(inventory: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    foreground_flow_ids = {
        item["id"] for item in inventory if item["entity_type"] == "Flow"
    }
    foreground_process_ids = {
        item["id"] for item in inventory if item["entity_type"] == "Process"
    }
    foreground_outputs: dict[str, set[str]] = {
        process_id: set() for process_id in foreground_process_ids
    }

    for item in inventory:
        if item["entity_type"] != "Process":
            continue
        process_data = item["data"]
        if "quantitativeReference" in process_data:
            errors.append(
                f"{item['path']}: uses unsupported field "
                "'quantitativeReference'; mark exactly one output exchange with "
                "boolean 'isQuantitativeReference: true'"
            )
        exchanges = process_data.get("exchanges", [])
        if not isinstance(exchanges, list):
            errors.append(f"{item['path']}: exchanges must be an array")
            continue
        quantitative_references: list[int] = []
        for index, exchange in enumerate(exchanges, start=1):
            if not isinstance(exchange, dict):
                errors.append(f"{item['path']}: exchanges[{index}] must be an object")
                continue
            if "input" in exchange:
                errors.append(
                    f"{item['path']}: exchanges[{index}] uses unsupported field "
                    "'input'; use boolean 'isInput'"
                )
            if "quantitativeReference" in exchange:
                errors.append(
                    f"{item['path']}: exchanges[{index}] uses unsupported field "
                    "'quantitativeReference'; use boolean "
                    "'isQuantitativeReference'"
                )
            if (
                "isQuantitativeReference" in exchange
                and not isinstance(exchange["isQuantitativeReference"], bool)
            ):
                errors.append(
                    f"{item['path']}: exchanges[{index}].isQuantitativeReference "
                    "must be a boolean when present"
                )
            is_input = exchange.get("isInput")
            if not isinstance(is_input, bool):
                errors.append(
                    f"{item['path']}: exchanges[{index}].isInput must be an "
                    "explicit boolean"
                )
                continue
            flow = exchange.get("flow")
            flow_id = flow.get("@id") if isinstance(flow, dict) else None
            if exchange.get("isQuantitativeReference") is True:
                quantitative_references.append(index)
                if is_input is not False:
                    errors.append(
                        f"{item['path']}: exchanges[{index}] quantitative "
                        "reference must be an output exchange"
                    )
                if not isinstance(flow_id, str) or not flow_id:
                    errors.append(
                        f"{item['path']}: exchanges[{index}] quantitative "
                        "reference requires a non-empty Flow @id"
                    )
            if is_input is False and isinstance(flow_id, str):
                foreground_outputs[item["id"]].add(flow_id)
        if len(quantitative_references) != 1:
            errors.append(
                f"{item['path']}: Process requires exactly one output exchange "
                "with boolean 'isQuantitativeReference: true'; found "
                f"{len(quantitative_references)}"
            )

    for item in inventory:
        if item["entity_type"] != "Process":
            continue
        for index, exchange in enumerate(item["data"].get("exchanges", []), start=1):
            if not isinstance(exchange, dict) or exchange.get("isInput") is not True:
                continue
            flow = exchange.get("flow")
            flow_id = flow.get("@id") if isinstance(flow, dict) else None
            provider = exchange.get("defaultProvider")
            provider_id = (
                provider.get("@id") if isinstance(provider, dict) else None
            )
            if flow_id not in foreground_flow_ids:
                continue
            if not provider_id:
                errors.append(
                    f"{item['path']}: exchanges[{index}] foreground input "
                    f"{flow_id} requires defaultProvider"
                )
                continue
            if provider.get("@type") != "Process":
                errors.append(
                    f"{item['path']}: exchanges[{index}].defaultProvider must "
                    "reference @type Process"
                )
            if provider_id not in foreground_process_ids:
                continue
            if flow_id not in foreground_outputs.get(provider_id, set()):
                errors.append(
                    f"{item['path']}: exchanges[{index}].defaultProvider "
                    f"{provider_id} does not output foreground Flow {flow_id}"
                )

    for item in inventory:
        if item["entity_type"] != "ProductSystem":
            continue
        data = item["data"]
        if data.get("linkingMode") != "auto":
            errors.append(
                f"{item['path']}: linkingMode must be explicitly set to 'auto'"
            )
        if data.get("preferDefaultProviders") is not True:
            errors.append(
                f"{item['path']}: preferDefaultProviders must be true"
            )
        ref_process = data.get("refProcess")
        ref_process_id = (
            ref_process.get("@id") if isinstance(ref_process, dict) else None
        )
        if ref_process_id not in foreground_process_ids:
            errors.append(
                f"{item['path']}: refProcess must reference a foreground Process"
            )
        expected = data.get("expectedProcessIds")
        if not isinstance(expected, list) or not expected:
            errors.append(
                f"{item['path']}: expectedProcessIds must be a non-empty array"
            )
        else:
            invalid_expected = sorted(
                {
                    str(process_id)
                    for process_id in expected
                    if not isinstance(process_id, str)
                    or process_id not in foreground_process_ids
                }
            )
            if invalid_expected:
                errors.append(
                    f"{item['path']}: expectedProcessIds must reference foreground "
                    f"Processes: {invalid_expected}"
                )
            if ref_process_id not in expected:
                errors.append(
                    f"{item['path']}: expectedProcessIds must include refProcess"
                )
        if "processes" in data:
            errors.append(
                f"{item['path']}: auto linking must not provide processes"
            )
        if "processLinks" in data:
            errors.append(
                f"{item['path']}: auto linking must not provide processLinks"
            )
    return errors


def _descriptor_record(entity_type: str, descriptor: object) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "id": getattr(descriptor, "id", None),
        "name": getattr(descriptor, "name", None),
        "category": getattr(descriptor, "category", None),
    }


def _ref_record(reference: object | None) -> dict[str, Any] | None:
    if reference is None:
        return None
    return {
        "id": getattr(reference, "id", None),
        "name": getattr(reference, "name", None),
    }


def _provider_requirements(
    inventory: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collect background provider expectations declared by foreground exchanges."""
    foreground_process_ids = {
        item["id"] for item in inventory if item["entity_type"] == "Process"
    }
    requirements: dict[tuple[str, str], dict[str, Any]] = {}
    for item in inventory:
        if item["entity_type"] != "Process":
            continue
        for exchange in item["data"].get("exchanges", []):
            if not isinstance(exchange, dict) or exchange.get("isInput") is not True:
                continue
            provider = exchange.get("defaultProvider")
            flow = exchange.get("flow")
            if not isinstance(provider, dict) or not isinstance(flow, dict):
                continue
            provider_id = provider.get("@id")
            flow_id = flow.get("@id")
            if (
                not isinstance(provider_id, str)
                or not provider_id
                or provider_id in foreground_process_ids
                or not isinstance(flow_id, str)
                or not flow_id
            ):
                continue
            key = (provider_id, flow_id)
            requirements[key] = {
                "provider_id": provider_id,
                "provider_name": provider.get("name"),
                "flow_id": flow_id,
                "flow_name": flow.get("name"),
                "expected_geography": exchange.get("expectedProviderGeography"),
                "source_process_id": item["id"],
                "source_path": item["path"],
            }
    return sorted(
        requirements.values(),
        key=lambda item: (
            item["provider_id"],
            item["flow_id"],
            item["source_process_id"],
        ),
    )


def _provider_checks(
    client: object,
    inventory: list[dict[str, Any]],
    database_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    descriptor_by_id = {
        record["id"]: record
        for record in database_records
        if record["entity_type"] == "Process" and record["id"]
    }
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    for requirement in _provider_requirements(inventory):
        provider_id = requirement["provider_id"]
        descriptor = descriptor_by_id.get(provider_id)
        check = {
            **requirement,
            "exists": descriptor is not None,
            "descriptor_name": descriptor.get("name") if descriptor else None,
            "category": descriptor.get("category") if descriptor else None,
            "location": None,
            "output_flow_match": False,
        }
        if descriptor is None:
            errors.append(
                f"{requirement['source_path']}: background provider {provider_id} "
                "was not found in the active database"
            )
            checks.append(check)
            continue
        try:
            provider = client.get(olca_schema.Process, provider_id)
        except Exception as exc:
            errors.append(
                f"{requirement['source_path']}: cannot read background provider "
                f"{provider_id}: {exc}"
            )
            checks.append(check)
            continue
        if provider is None:
            errors.append(
                f"{requirement['source_path']}: background provider {provider_id} "
                "descriptor exists but the Process cannot be read"
            )
            checks.append(check)
            continue
        location = _ref_record(getattr(provider, "location", None))
        check["location"] = location
        output_flow_ids = sorted(
            {
                getattr(getattr(exchange, "flow", None), "id", None)
                for exchange in list(getattr(provider, "exchanges", None) or [])
                if getattr(exchange, "is_input", None) is not True
                and getattr(getattr(exchange, "flow", None), "id", None)
            }
        )
        check["output_flow_ids"] = output_flow_ids
        check["output_flow_match"] = requirement["flow_id"] in output_flow_ids
        if not check["output_flow_match"]:
            errors.append(
                f"{requirement['source_path']}: provider {provider_id} does not "
                f"output referenced flow {requirement['flow_id']}"
            )
        expected_geography = requirement["expected_geography"]
        if isinstance(expected_geography, str) and expected_geography.strip():
            actual_values = {
                str(value).casefold()
                for value in (
                    (location or {}).get("id"),
                    (location or {}).get("name"),
                )
                if value
            }
            check["geography_match"] = (
                expected_geography.strip().casefold() in actual_values
            )
        checks.append(check)
    return checks, errors


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
    return "", "missing"


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
    errors.extend(_lci_semantic_errors(inventory))
    active_database, identity_source = _active_database_label(endpoint, database_name)
    if not active_database:
        errors.append(
            "Active database identity is required; pass database_name or set "
            "OPENLCA_DATABASE_NAME"
        )

    if errors:
        return (
            {
                "schema": "whole-lca/import-preflight",
                "version": "1.1",
                "ok": False,
                "status": "invalid_lci",
                "endpoint": endpoint,
                "active_database": active_database or "unknown",
                "database_identity_source": identity_source,
                "database_fingerprint": None,
                "lci_fingerprint": None,
                "target_scope_fingerprint": None,
                "background_provider_fingerprint": None,
                "background_provider_checks": [],
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

    owns_client = client is None
    ipc_client = client or create_ipc_client(host, port)
    try:
        database_records, target_descriptors = _database_snapshot(ipc_client, category)
    except Exception as exc:
        if owns_client:
            close_ipc_client(ipc_client)
        raise RuntimeError(f"Failed to inspect active openLCA database at {endpoint}: {exc}") from exc

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
    provider_checks, provider_errors = _provider_checks(
        ipc_client,
        inventory,
        database_records,
    )
    if owns_client:
        close_ipc_client(ipc_client)
    lci_fingerprint = stable_hash(planned_entities)
    target_scope_fingerprint = stable_hash(overwrite_scope)
    background_provider_fingerprint = stable_hash(provider_checks)
    hash_payload = {
        "version": "1.1",
        "endpoint": endpoint,
        "active_database": active_database,
        "target_category": category,
        "lci_fingerprint": lci_fingerprint,
        "target_scope_fingerprint": target_scope_fingerprint,
        "background_provider_fingerprint": background_provider_fingerprint,
    }
    preflight_hash = stable_hash(hash_payload)
    ok = not provider_errors
    return (
        {
            "schema": "whole-lca/import-preflight",
            "version": "1.1",
            "ok": ok,
            "status": "ready" if ok else "invalid_references",
            "endpoint": endpoint,
            "active_database": active_database,
            "database_identity_source": identity_source,
            "database_fingerprint": stable_hash(
                {
                    "active_database": active_database,
                    "target_scope_fingerprint": target_scope_fingerprint,
                    "background_provider_fingerprint": background_provider_fingerprint,
                }
            ),
            "lci_fingerprint": lci_fingerprint,
            "target_scope_fingerprint": target_scope_fingerprint,
            "background_provider_fingerprint": background_provider_fingerprint,
            "background_provider_checks": provider_checks,
            "lci_dir": str(root),
            "target_category": category,
            "planned_entities": planned_entities,
            "overwrite_delete_scope": overwrite_scope,
            "counts": {
                "planned": len(planned_entities),
                "overwrite_or_delete": len(overwrite_scope),
            },
            "errors": provider_errors,
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


def _put_product_system(
    client: object,
    entity: olca_schema.ProductSystem,
    source_data: dict[str, Any],
) -> object:
    """Create a Product System through openLCA's official auto-linking API."""
    if source_data.get("linkingMode") != "auto":
        raise ValueError("ProductSystem linkingMode must be 'auto'")
    if source_data.get("preferDefaultProviders") is not True:
        raise ValueError("ProductSystem preferDefaultProviders must be true")

    ref_process = getattr(entity, "ref_process", None)
    if ref_process is None or not getattr(ref_process, "id", None):
        raise ValueError("ProductSystem requires refProcess for automatic linking")

    prefer_defaults = source_data.get("preferDefaultProviders", True)
    provider_linking = (
        olca_schema.ProviderLinking.PREFER_DEFAULTS
        if prefer_defaults is not False
        else olca_schema.ProviderLinking.IGNORE_DEFAULTS
    )
    config = olca_schema.LinkingConfig(
        prefer_unit_processes=False,
        provider_linking=provider_linking,
    )

    generated_ref = client.create_product_system(ref_process, config)
    generated_id = getattr(generated_ref, "id", None)
    if not generated_id:
        raise RuntimeError("IPC Server did not create an auto-linked ProductSystem")

    try:
        generated = client.get(olca_schema.ProductSystem, generated_id)
        if generated is None:
            raise RuntimeError(
                f"IPC Server could not read generated ProductSystem {generated_id}"
            )

        for field in ("processes", "process_links"):
            value = getattr(generated, field, None)
            if value is not None:
                setattr(entity, field, value)
        for field in (
            "ref_exchange",
            "ref_process",
            "target_amount",
            "target_flow_property",
            "target_unit",
        ):
            if getattr(entity, field, None) is not None:
                continue
            value = getattr(generated, field, None)
            if value is not None:
                setattr(entity, field, value)

        reference = client.put(entity)
        if reference is None:
            raise RuntimeError("IPC Server did not return an entity reference")
    except Exception as exc:
        try:
            client.delete(generated_ref)
        except Exception as cleanup_exc:
            raise RuntimeError(
                f"{exc}; additionally could not delete temporary ProductSystem "
                f"{generated_id}: {cleanup_exc}"
            ) from exc
        raise

    if generated_id != getattr(reference, "id", None):
        try:
            client.delete(generated_ref)
        except Exception as exc:
            raise RuntimeError(
                f"saved ProductSystem but could not delete temporary system "
                f"{generated_id}: {exc}"
            ) from exc
    return reference


def _execute_import(
    client: object,
    inventory: list[dict[str, Any]],
    target_descriptors: list[tuple[str, object]],
    target_category: str,
    emit: Callable[[str], None] | None = None,
    on_progress: (
        Callable[[list[dict[str, Any]], int, int, int, list[str]], None] | None
    ) = None,
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
            transport_failed = False
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
                transport_failed = is_transport_error(exc)
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
            if on_progress is not None:
                on_progress(records, imported, failed, deleted, errors)
            if transport_failed:
                return records, imported, failed, deleted, errors

    for item in inventory:
        output(f"正在处理文件: {item['path']}...")
        transport_failed = False
        try:
            entity = _deserialize_entity(item, target_category)
            if isinstance(entity, olca_schema.ProductSystem):
                reference = _put_product_system(client, entity, item["data"])
            else:
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
            transport_failed = is_transport_error(exc)
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
        if on_progress is not None:
            on_progress(records, imported, failed, deleted, errors)
        if transport_failed:
            return records, imported, failed, deleted, errors
    return records, imported, failed, deleted, errors


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _operation_path(operation_dir: Path, preflight_hash: str) -> Path:
    return operation_dir / f"{preflight_hash}.json"


def get_import_operation(
    operation_dir: Path,
    preflight_hash: str,
) -> dict[str, Any]:
    """Read a persisted import operation without touching openLCA."""
    if (
        len(preflight_hash) != 64
        or any(character not in "0123456789abcdef" for character in preflight_hash)
    ):
        raise ValueError("preflight_hash must be a lowercase 64-character SHA-256")
    path = _operation_path(operation_dir, preflight_hash)
    if not path.is_file():
        return {
            "schema": "whole-lca/import-operation-status",
            "version": "1.0",
            "status": "not_found",
            "preflight_hash": preflight_hash,
            "report": None,
        }
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": "whole-lca/import-operation-status",
            "version": "1.0",
            "status": "indeterminate",
            "preflight_hash": preflight_hash,
            "report": None,
            "error": str(exc),
        }
    status = report.get("status")
    return {
        "schema": "whole-lca/import-operation-status",
        "version": "1.0",
        "status": (
            status
            if status
            in {"running", "success", "partial_failure", "failed", "rejected"}
            else "indeterminate"
        ),
        "preflight_hash": preflight_hash,
        "report": report,
    }


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
        "version": "1.1",
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
    database_name: str | None = None,
    client: object | None = None,
    operation_dir: Path | None = None,
) -> dict[str, Any]:
    """Import LCI only after verifying an unchanged preflight hash."""
    if (
        not isinstance(preflight_hash, str)
        or len(preflight_hash) != 64
        or any(character not in "0123456789abcdef" for character in preflight_hash)
    ):
        raise ValueError("preflight_hash must be a lowercase 64-character SHA-256")
    started_at = utc_now()
    started_clock = time.monotonic()
    operation_id = str(uuid.uuid4())
    endpoint = build_endpoint(host, port)
    active_database, _ = _active_database_label(endpoint, database_name)
    operation_path = (
        _operation_path(operation_dir, preflight_hash)
        if operation_dir is not None
        else None
    )
    if operation_dir is not None:
        existing = get_import_operation(operation_dir, preflight_hash)
        if existing["status"] in {"running", "success", "partial_failure", "failed"}:
            return existing["report"]

    owns_client = client is None
    ipc_client = client or create_ipc_client(
        host,
        port,
        timeout=LONG_REQUEST_TIMEOUT,
    )
    current, inventory, target_descriptors = _inspect_import(
        host=host,
        port=port,
        lci_dir=lci_dir,
        target_category=target_category,
        database_name=database_name,
        client=ipc_client,
    )
    if not current["ok"]:
        report = _rejected_import_report(
            endpoint,
            active_database,
            target_category,
            preflight_hash,
            started_at,
            started_clock,
            ["Import rejected: current preflight is not ready.", *current["errors"]],
        )
        if operation_dir is not None:
            _write_json_atomic(_operation_path(operation_dir, preflight_hash), report)
        if owns_client:
            close_ipc_client(ipc_client)
        return report
    if current["preflight_hash"] != preflight_hash:
        report = _rejected_import_report(
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
                f"current_lci_fingerprint={current['lci_fingerprint']}",
                f"current_target_scope_fingerprint={current['target_scope_fingerprint']}",
                "current_background_provider_fingerprint="
                f"{current['background_provider_fingerprint']}",
            ],
        )
        if operation_dir is not None:
            _write_json_atomic(_operation_path(operation_dir, preflight_hash), report)
        if owns_client:
            close_ipc_client(ipc_client)
        return report

    def report_value(
        status: str,
        records: list[dict[str, Any]],
        imported: int,
        failed: int,
        deleted: int,
        errors: list[str],
        *,
        ended_at: str | None,
    ) -> dict[str, Any]:
        return {
            "schema": "whole-lca/import-report",
            "version": "1.1",
            "operation_id": operation_id,
            "status": status,
            "endpoint": endpoint,
            "active_database": current["active_database"],
            "target_category": target_category,
            "preflight_hash": preflight_hash,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": max(
                0, round((time.monotonic() - started_clock) * 1000)
            ),
            "success_count": imported,
            "failed_count": failed,
            "deleted_count": deleted,
            "entities": list(records),
            "errors": list(errors),
        }

    if operation_path is not None:
        _write_json_atomic(
            operation_path,
            report_value("running", [], 0, 0, 0, [], ended_at=None),
        )

    def persist_progress(
        records: list[dict[str, Any]],
        imported: int,
        failed: int,
        deleted: int,
        errors: list[str],
    ) -> None:
        if operation_path is not None:
            _write_json_atomic(
                operation_path,
                report_value(
                    "running",
                    records,
                    imported,
                    failed,
                    deleted,
                    errors,
                    ended_at=None,
                ),
            )

    records, imported, failed, deleted, errors = _execute_import(
        client=ipc_client,
        inventory=inventory,
        target_descriptors=target_descriptors,
        target_category=target_category,
        on_progress=persist_progress,
    )
    status = "success" if failed == 0 and imported == len(inventory) else "partial_failure"
    if imported == 0 and failed:
        status = "failed"
    report = report_value(
        status,
        records,
        imported,
        failed,
        deleted,
        errors,
        ended_at=utc_now(),
    )
    if operation_path is not None:
        _write_json_atomic(operation_path, report)
    if owns_client:
        close_ipc_client(ipc_client)
    return report


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
    expected_process_ids: list[str] | None = None,
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
    graph_fingerprint = stable_hash(
        {
            "nodes": sorted(node_ids),
            "edges": sorted(
                (
                    str(edge["provider"]["id"] or ""),
                    str(edge["flow"]["id"] or ""),
                    str(edge["process"]["id"] or ""),
                )
                for edge in edges
            ),
        }
    )
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
        "graph_fingerprint": graph_fingerprint,
        "timestamp": utc_now(),
        "error": error,
    }


def get_model_graph(
    host: str,
    port: int,
    product_system: str,
    client: object | None = None,
    expected_process_ids: list[str] | None = None,
) -> dict[str, Any]:
    endpoint = build_endpoint(host, port)
    owns_client = client is None
    ipc_client = client or create_ipc_client(host, port)
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
            "graph_fingerprint": stable_hash({"nodes": [], "edges": []}),
            "timestamp": utc_now(),
            "error": f"Product System not found: {product_system}",
        }
        if owns_client:
            close_ipc_client(ipc_client)
        return result
    system_id = getattr(system, "id", None)
    if system_id:
        loaded = ipc_client.get(olca_schema.ProductSystem, system_id)
        if loaded is not None:
            system = loaded
    result = model_graph_from_product_system(
        system,
        endpoint,
        expected_process_ids=expected_process_ids,
    )
    if owns_client:
        close_ipc_client(ipc_client)
    return result


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
    owns_client = client is None
    ipc_client = client or create_ipc_client(
        host,
        port,
        timeout=LONG_REQUEST_TIMEOUT,
    )
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
        failed_result = {
            **base,
            "status": "failed",
            "ended_at": utc_now(),
            "error": f"{missing} not found",
        }
        if owns_client:
            close_ipc_client(ipc_client)
        return failed_result

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

    calculation = {
        **base,
        "status": status,
        "impact_categories": impacts,
        "resource_released": released,
        "ended_at": utc_now(),
        "error": error,
    }
    if owns_client:
        close_ipc_client(ipc_client)
    return calculation
