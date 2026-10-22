from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import olca_schema

from .protocols import OpenLcaClient
from .readonly import (
    category_outside_project,
)


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
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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

    contained_paths: list[Path] = []
    for path in paths:
        relative_path = path.relative_to(root).as_posix()
        if path.is_symlink():
            errors.append(f"{relative_path}: LCI entity must not be a symbolic link")
            continue
        try:
            resolved = path.resolve()
        except OSError as exc:
            errors.append(f"{relative_path}: cannot resolve path: {exc}")
            continue
        if resolved != root and root not in resolved.parents:
            errors.append(f"{relative_path}: LCI entity path escapes LCI root")
            continue
        contained_paths.append(path)

    allowed_paths = {path.resolve() for path in contained_paths}
    for path in sorted(root.rglob("*.json")):
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved not in allowed_paths:
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                rel = str(path)
            errors.append(
                f"{rel}: JSON files are only allowed "
                "directly under flows/, processes/, or product_systems/"
            )

    if not contained_paths:
        errors.append(f"No entity JSON files found in LCI directory: {root}")
        return [], errors

    inventory: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in contained_paths:
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
            errors.append(f"{relative_path}: @context must be {JSON_LD_CONTEXT!r}")
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

    inventory = _sort_inventory_for_import(inventory)
    return inventory, errors


def _foreground_process_ids(inventory: list[dict[str, Any]]) -> set[str]:
    return {item["id"] for item in inventory if item["entity_type"] == "Process"}


def _topologically_sort_process_items(
    processes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Import foreground defaultProvider processes before their consumers."""
    by_id = {item["id"]: item for item in processes}
    process_ids = set(by_id)
    dependents: dict[str, set[str]] = {process_id: set() for process_id in process_ids}
    indegree: dict[str, int] = {process_id: 0 for process_id in process_ids}
    for item in processes:
        consumer_id = item["id"]
        for exchange in item["data"].get("exchanges", []):
            if not isinstance(exchange, dict) or exchange.get("isInput") is not True:
                continue
            provider_id = _exchange_provider_id(exchange)
            if not provider_id or provider_id not in process_ids:
                continue
            if consumer_id not in dependents[provider_id]:
                dependents[provider_id].add(consumer_id)
                indegree[consumer_id] += 1

    def path_key(process_id: str) -> str:
        return str(by_id[process_id]["path"])

    ready = sorted(
        [process_id for process_id in process_ids if indegree[process_id] == 0],
        key=path_key,
    )
    ordered_ids: list[str] = []
    while ready:
        current_id = ready.pop(0)
        ordered_ids.append(current_id)
        for dependent_id in sorted(dependents[current_id], key=path_key):
            indegree[dependent_id] -= 1
            if indegree[dependent_id] == 0:
                ready.append(dependent_id)
                ready.sort(key=path_key)
    if len(ordered_ids) != len(process_ids):
        remaining = sorted(process_ids - set(ordered_ids), key=path_key)
        ordered_ids.extend(remaining)
    return [by_id[process_id] for process_id in ordered_ids]


def _sort_inventory_for_import(
    inventory: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    order = {name: index for index, name in enumerate(ENTITY_IMPORT_ORDER)}
    buckets: dict[str, list[dict[str, Any]]] = {
        entity_type: [] for entity_type in ENTITY_IMPORT_ORDER
    }
    for item in inventory:
        buckets[item["entity_type"]].append(item)
    for entity_type in buckets:
        if entity_type != "Process":
            buckets[entity_type].sort(key=lambda row: row["path"])
    buckets["Process"] = _topologically_sort_process_items(buckets["Process"])
    sorted_inventory: list[dict[str, Any]] = []
    for entity_type in ENTITY_IMPORT_ORDER:
        sorted_inventory.extend(buckets[entity_type])
    return sorted_inventory


def validate_lci_directory(json_dir: Path) -> dict[str, Any]:
    """Return a deterministic, offline Stage 03/04 LCI validation result."""
    inventory, errors = load_lci_inventory(json_dir)
    counts = {
        entity_type: sum(1 for item in inventory if item["entity_type"] == entity_type)
        for entity_type in LCI_ENTITY_DIRECTORIES.values()
    }
    required_missing = [
        entity_type for entity_type, count in counts.items() if count == 0
    ]
    for entity_type in required_missing:
        errors.append(f"LCI inventory requires at least one {entity_type} entity")
    errors.extend(_lci_semantic_errors(inventory))
    root = json_dir.resolve()
    mapping_path = root / "human_readable_mapping.md"
    if mapping_path.is_symlink():
        errors.append("human_readable_mapping.md must not be a symbolic link")
    elif not mapping_path.is_file():
        errors.append(
            "LCI inventory requires human_readable_mapping.md at the LCI root"
        )
    else:
        try:
            resolved = mapping_path.resolve()
        except OSError as exc:
            errors.append(f"human_readable_mapping.md: cannot resolve path: {exc}")
        else:
            if resolved != root and root not in resolved.parents:
                errors.append("human_readable_mapping.md path escapes LCI root")
    return {
        "schema": "openlca/lci-validation",
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
    foreground_process_ids = _foreground_process_ids(inventory)
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
            if "isQuantitativeReference" in exchange and not isinstance(
                exchange["isQuantitativeReference"], bool
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
            provider_id = provider.get("@id") if isinstance(provider, dict) else None
            if flow_id not in foreground_flow_ids:
                continue
            if not provider_id:
                errors.append(
                    f"{item['path']}: exchanges[{index}] foreground input "
                    f"{flow_id} requires defaultProvider"
                )
                continue
            if isinstance(provider, dict) and provider.get("@type") != "Process":
                errors.append(
                    f"{item['path']}: exchanges[{index}].defaultProvider must "
                    "reference @type Process"
                )
            if provider_id not in foreground_process_ids:
                continue
            if flow_id not in foreground_outputs.get(provider_id, set()):
                errors.append(
                    f"{item['path']}: exchanges[{index}].defaultProvider "
                    f"Process {provider_id} 未以定量参考输出前景流 {flow_id}；"
                    "请核对 provider 过程的输出 exchange 与输入流一致"
                )

    for item in inventory:
        if item["entity_type"] != "ProductSystem":
            continue
        data = item["data"]
        linking_mode = data.get("linkingMode")
        if linking_mode not in {"auto", "explicit"}:
            errors.append(
                f"{item['path']}: linkingMode must be 'auto' or 'explicit'"
            )
            continue
        if data.get("preferDefaultProviders") is not True:
            errors.append(f"{item['path']}: preferDefaultProviders must be true")
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
        if linking_mode == "auto":
            if "processes" in data:
                errors.append(f"{item['path']}: auto linking must not provide processes")
            if "processLinks" in data:
                errors.append(
                    f"{item['path']}: auto linking must not provide processLinks"
                )
        else:
            if "processes" in data or "processLinks" in data:
                errors.append(
                    f"{item['path']}: explicit linking must not provide processes "
                    "or processLinks; the host builds them from defaultProvider"
                )
            expected_ids = [
                process_id
                for process_id in (expected or [])
                if isinstance(process_id, str)
            ]
            missing_providers = _foreground_technosphere_missing_providers(
                inventory, expected_ids
            )
            if missing_providers:
                errors.append(
                    f"{item['path']}: explicit linking requires defaultProvider on "
                    f"every technosphere product input of foreground processes: "
                    f"{missing_providers}"
                )
    return errors


def _exchange_flow_id(exchange: dict[str, Any]) -> str | None:
    flow = exchange.get("flow")
    return flow.get("@id") if isinstance(flow, dict) else None


def _exchange_provider_id(exchange: dict[str, Any]) -> str | None:
    provider = exchange.get("defaultProvider")
    return provider.get("@id") if isinstance(provider, dict) else None


def _foreground_flow_ids(inventory: list[dict[str, Any]]) -> set[str]:
    return {item["id"] for item in inventory if item["entity_type"] == "Flow"}


def _is_technosphere_input(
    exchange: dict[str, Any], foreground_flow_ids: set[str]
) -> bool:
    if exchange.get("isInput") is not True:
        return False
    if _exchange_provider_id(exchange):
        return True
    flow_id = _exchange_flow_id(exchange)
    return bool(flow_id and flow_id in foreground_flow_ids)


def _collect_unlinked_inputs(
    inventory: list[dict[str, Any]],
    process_ids: list[str],
) -> list[dict[str, Any]]:
    """Elementary inputs without defaultProvider (non-foreground flows)."""
    foreground_flow_ids = _foreground_flow_ids(inventory)
    allowed = set(process_ids)
    unlinked: list[dict[str, Any]] = []
    for item in inventory:
        if item["entity_type"] != "Process" or item["id"] not in allowed:
            continue
        for index, exchange in enumerate(item["data"].get("exchanges", []), start=1):
            if not isinstance(exchange, dict) or exchange.get("isInput") is not True:
                continue
            if _exchange_provider_id(exchange):
                continue
            flow_id = _exchange_flow_id(exchange)
            if flow_id and flow_id in foreground_flow_ids:
                continue
            unlinked.append(
                {
                    "path": item["path"],
                    "process_id": item["id"],
                    "exchange_index": index,
                    "flow_id": flow_id,
                }
            )
    return unlinked


def _foreground_technosphere_missing_providers(
    inventory: list[dict[str, Any]],
    process_ids: list[str],
) -> list[str]:
    """Foreground-flow technosphere inputs that lack defaultProvider."""
    foreground_flow_ids = _foreground_flow_ids(inventory)
    allowed = set(process_ids)
    missing: list[str] = []
    for item in inventory:
        if item["entity_type"] != "Process" or item["id"] not in allowed:
            continue
        path = item["path"]
        for index, exchange in enumerate(item["data"].get("exchanges", []), start=1):
            if not isinstance(exchange, dict) or exchange.get("isInput") is not True:
                continue
            flow_id = _exchange_flow_id(exchange)
            if flow_id not in foreground_flow_ids:
                continue
            if not _exchange_provider_id(exchange):
                missing.append(f"{path}: exchanges[{index}]")
    return missing


def _preflight_foreground_provider_reference_errors(
    inventory: list[dict[str, Any]],
    *,
    background_process_ids: set[str] | None = None,
) -> list[str]:
    """Offline checks for foreground defaultProvider references in LCI JSON."""
    foreground_process_ids = _foreground_process_ids(inventory)
    background_ids = background_process_ids or set()
    foreground_outputs: dict[str, set[str]] = {
        process_id: set() for process_id in foreground_process_ids
    }
    for item in inventory:
        if item["entity_type"] != "Process":
            continue
        for exchange in item["data"].get("exchanges", []):
            if not isinstance(exchange, dict) or exchange.get("isInput") is True:
                continue
            if exchange.get("isQuantitativeReference") is True:
                flow = exchange.get("flow")
                flow_id = flow.get("@id") if isinstance(flow, dict) else None
                if isinstance(flow_id, str) and flow_id:
                    foreground_outputs[item["id"]].add(flow_id)
    errors: list[str] = []
    foreground_flow_ids = _foreground_flow_ids(inventory)
    for item in inventory:
        if item["entity_type"] != "Process":
            continue
        for index, exchange in enumerate(item["data"].get("exchanges", []), start=1):
            if not isinstance(exchange, dict) or exchange.get("isInput") is not True:
                continue
            flow = exchange.get("flow")
            flow_id = flow.get("@id") if isinstance(flow, dict) else None
            provider = exchange.get("defaultProvider")
            provider_id = provider.get("@id") if isinstance(provider, dict) else None
            if not isinstance(flow_id, str) or not flow_id:
                continue
            if flow_id not in foreground_flow_ids:
                continue
            if not provider_id:
                continue
            if provider_id in foreground_process_ids:
                if flow_id not in foreground_outputs.get(provider_id, set()):
                    errors.append(
                        f"{item['path']}: exchanges[{index}] 前景 provider Process "
                        f"{provider_id} 未以定量参考输出流 {flow_id}"
                    )
                continue
            if provider_id not in background_ids:
                errors.append(
                    f"{item['path']}: exchanges[{index}] defaultProvider Process "
                    f"{provider_id} 既不在本批 LCI 前景过程中，也未在预检数据库 Process "
                    "描述符中找到；请改用 validate_providers_batch 核实的背景数据集"
                )
    return errors


def _exchange_needs_foreground_provider_repair(
    saved: olca_schema.Process,
    *,
    flow_id: str,
    provider_id: str,
) -> bool:
    for exchange in list(getattr(saved, "exchanges", None) or []):
        if getattr(exchange, "is_input", None) is not True:
            continue
        ex_flow = getattr(getattr(exchange, "flow", None), "id", None)
        if ex_flow != flow_id:
            continue
        ex_provider = getattr(getattr(exchange, "default_provider", None), "id", None)
        return ex_provider != provider_id
    return True


def _repair_foreground_process_providers(
    client: OpenLcaClient,
    inventory: list[dict[str, Any]],
    target_category: str,
) -> list[str]:
    """Re-put foreground processes whose defaultProvider refs were dropped on first import."""
    foreground_process_ids = _foreground_process_ids(inventory)
    errors: list[str] = []
    for item in inventory:
        if item["entity_type"] != "Process":
            continue
        process_id = item["id"]
        expected: list[tuple[str, str]] = []
        for exchange in item["data"].get("exchanges", []):
            if not isinstance(exchange, dict) or exchange.get("isInput") is not True:
                continue
            flow = exchange.get("flow") or {}
            flow_id = flow.get("@id")
            provider_id = _exchange_provider_id(exchange)
            if (
                not isinstance(flow_id, str)
                or not flow_id
                or not provider_id
                or provider_id not in foreground_process_ids
            ):
                continue
            expected.append((flow_id, provider_id))
        if not expected:
            continue
        saved = client.get(olca_schema.Process, process_id)
        if saved is None:
            errors.append(
                f"前景 Process {process_id} ({item['path']}) 尚未导入，无法修复 defaultProvider"
            )
            continue
        saved_category = getattr(saved, "category", None)
        saved_category_text = (
            saved_category if isinstance(saved_category, str) else None
        )
        if category_outside_project(saved_category_text, target_category):
            errors.append(
                f"{item['path']}: @id {process_id} 已存在且不在本项目分类，"
                "只能在交换里引用，不能作为导入文件"
            )
            continue
        needs_repair = any(
            _exchange_needs_foreground_provider_repair(
                saved, flow_id=flow_id, provider_id=provider_id
            )
            for flow_id, provider_id in expected
        )
        if not needs_repair:
            continue
        entity = _deserialize_entity(item, target_category)
        assert isinstance(entity, olca_schema.Process)
        client.put(entity)
        saved_after = client.get(olca_schema.Process, process_id)
        if saved_after is None:
            errors.append(
                f"修复 defaultProvider 后无法读回 Process {process_id} ({item['path']})"
            )
            continue
        for flow_id, provider_id in expected:
            if _exchange_needs_foreground_provider_repair(
                saved_after, flow_id=flow_id, provider_id=provider_id
            ):
                errors.append(
                    f"Process {process_id} ({item['name']}) 交换 flow={flow_id} "
                    f"仍缺少 defaultProvider={provider_id}；"
                    "openLCA 在 provider 过程不存在时静默丢弃链接，"
                    "请确认导入顺序与 provider 修复已执行"
                )
    return errors


def build_entity_plan(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-entity import plan persisted on the operation record."""
    return [
        {
            "path": item["path"],
            "entity_type": item["entity_type"],
            "id": item["id"],
            "name": item["name"],
            "content_hash": item.get("sha256", ""),
            "status": "pending",
        }
        for item in inventory
    ]


def _plan_by_id(plan: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(entry["id"]): entry for entry in plan}


def _deserialize_entity(item: dict[str, Any], target_category: str) -> object:
    entity = ENTITY_TYPES[item["entity_type"]].from_dict(item["data"])
    if hasattr(entity, "category"):
        entity.category = target_category
    return entity


def _write_json_atomic(path: Path, value: dict[str, Any], *, durable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if durable:
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
    temporary.replace(path)
    if durable:
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
