from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import olca_schema

from .connection import (
    build_endpoint,
    close_ipc_client,
    create_ipc_client,
    is_transport_error,
)
from .ipc_failure import on_ipc_transport_failure
from .timeout_policy import ipc_read_scope, product_system_read_sec
from .protocols import OlcaDescriptor, OpenLcaClient
from .readonly import (
    _provider_output_unit,
    category_outside_project,
)
from .lci_inventory import (
    ENTITY_DELETE_ORDER,
    ENTITY_TYPES,
    _collect_unlinked_inputs,
    _deserialize_entity,
    _exchange_provider_id,
    _foreground_flow_ids,
    _foreground_technosphere_missing_providers,
    _is_technosphere_input,
    _lci_semantic_errors,
    _plan_by_id,
    _preflight_foreground_provider_reference_errors,
    _repair_foreground_process_providers,
    build_entity_plan,
    load_lci_inventory,
    stable_hash,
    utc_now,
)


def _entity_openlca_fingerprint(
    entity: object, entity_type: str, content_hash: str
) -> str:
    """Stable fingerprint for reconcile: prefer source hash when entity matches."""
    name = getattr(entity, "name", None)
    entity_id = getattr(entity, "id", None)
    payload: dict[str, Any] = {
        "entity_type": entity_type,
        "id": entity_id,
        "name": name,
        "content_hash": content_hash,
    }
    if entity_type == "ProductSystem":
        payload["ref_process"] = getattr(
            getattr(entity, "ref_process", None), "id", None
        )
        payload["process_count"] = len(getattr(entity, "processes", None) or [])
        payload["link_count"] = len(getattr(entity, "process_links", None) or [])
    return stable_hash(payload)


def _foreground_process_data(
    inventory: list[dict[str, Any]], process_id: str
) -> dict[str, Any] | None:
    for item in inventory:
        if item["entity_type"] == "Process" and item["id"] == process_id:
            return item["data"]
    return None


def _all_foreground_technosphere_have_providers(
    inventory: list[dict[str, Any]], process_ids: list[str]
) -> bool:
    return not _foreground_technosphere_missing_providers(inventory, process_ids)


def _foreground_has_technosphere_inputs(
    inventory: list[dict[str, Any]], process_ids: list[str]
) -> bool:
    foreground_flow_ids = _foreground_flow_ids(inventory)
    allowed = set(process_ids)
    for item in inventory:
        if item["entity_type"] != "Process" or item["id"] not in allowed:
            continue
        for exchange in item["data"].get("exchanges", []):
            if isinstance(exchange, dict) and _is_technosphere_input(
                exchange, foreground_flow_ids
            ):
                return True
    return False


def _amounts_match(stored: object, expected: object) -> bool:
    if isinstance(stored, bool) or isinstance(expected, bool):
        return False
    if not isinstance(stored, (int, float)) or not isinstance(expected, (int, float)):
        return stored == expected
    return abs(float(stored) - float(expected)) <= 1e-9 * max(
        1.0, abs(float(stored)), abs(float(expected))
    )


def _process_type_label(process: object) -> str | None:
    process_type = getattr(process, "process_type", None)
    if process_type is None:
        return None
    return getattr(process_type, "value", str(process_type))


def _read_saved_process(
    client: OpenLcaClient, process_id: str
) -> olca_schema.Process:
    saved = client.get(olca_schema.Process, process_id)
    if saved is None:
        raise ValueError(
            f"foreground Process {process_id} must be imported before ProductSystem"
        )
    return saved


def _match_saved_input_exchange(
    saved: olca_schema.Process,
    *,
    process_id: str,
    flow_id: str,
    provider_id: str,
    amount: object,
) -> olca_schema.Exchange:
    matches: list[olca_schema.Exchange] = []
    same_flow: list[tuple[olca_schema.Exchange, str | None]] = []
    for exchange in list(getattr(saved, "exchanges", None) or []):
        if getattr(exchange, "is_input", None) is not True:
            continue
        ex_flow = getattr(getattr(exchange, "flow", None), "id", None)
        ex_provider = getattr(getattr(exchange, "default_provider", None), "id", None)
        if ex_flow == flow_id:
            same_flow.append((exchange, ex_provider))
        if ex_flow != flow_id or ex_provider != provider_id:
            continue
        matches.append(exchange)
    # Amount is only a tie-breaker: import may convert units (e.g. kg*km -> t*km),
    # so the stored amount can legitimately differ from the source JSON.
    if len(matches) > 1:
        narrowed = [
            ex for ex in matches if _amounts_match(getattr(ex, "amount", None), amount)
        ]
        if narrowed:
            matches = narrowed
    if len(matches) == 1:
        return matches[0]
    if not matches:
        if same_flow:
            stored = sorted({stored_provider for _, stored_provider in same_flow})
            raise ValueError(
                f"Process {process_id} 已导入的交换与 LCI 技术输入不匹配："
                f"flow={flow_id} 期望 defaultProvider={provider_id}，"
                f"数据库中为 stored provider={stored!r}。"
                "这通常是导入顺序导致 openLCA 静默丢弃 defaultProvider，"
                "而非 LCI 内容缺少该输入；请 reconcile 后重试 import 或检查 provider 修复日志。"
            )
        raise ValueError(
            f"no imported exchange on Process {process_id} matches technosphere "
            f"input flow={flow_id} provider={provider_id} amount={amount!r}"
        )
    raise ValueError(
        f"ambiguous imported exchanges on Process {process_id} for "
        f"flow={flow_id} provider={provider_id} amount={amount!r}"
    )


def _match_saved_output_exchange(
    saved: olca_schema.Process,
    *,
    process_id: str,
    flow_id: str,
    amount: object,
) -> olca_schema.Exchange:
    matches: list[olca_schema.Exchange] = []
    for exchange in list(getattr(saved, "exchanges", None) or []):
        if getattr(exchange, "is_quantitative_reference", None) is not True:
            continue
        ex_flow = getattr(getattr(exchange, "flow", None), "id", None)
        if ex_flow != flow_id:
            continue
        if amount is not None and not _amounts_match(
            getattr(exchange, "amount", None), amount
        ):
            continue
        matches.append(exchange)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(
            f"no quantitative-reference output on Process {process_id} "
            f"for flow={flow_id}"
        )
    raise ValueError(
        f"ambiguous quantitative-reference outputs on Process {process_id} "
        f"for flow={flow_id}"
    )


def _provider_types_for_ids(
    client: OpenLcaClient, provider_ids: set[str]
) -> dict[str, str | None]:
    types: dict[str, str | None] = {}
    for provider_id in sorted(provider_ids):
        try:
            provider = client.get(olca_schema.Process, provider_id)
        except Exception as exc:
            raise ValueError(f"cannot read provider Process {provider_id}: {exc}") from exc
        if provider is None:
            raise ValueError(f"provider Process {provider_id} was not found in database")
        types[provider_id] = _process_type_label(provider)
    return types


def _unit_process_providers(provider_types: dict[str, str | None]) -> list[str]:
    return sorted(
        provider_id
        for provider_id, label in provider_types.items()
        if label == olca_schema.ProcessType.UNIT_PROCESS.value
    )


def _build_explicit_product_system(
    client: OpenLcaClient,
    entity: olca_schema.ProductSystem,
    source_data: dict[str, Any],
    inventory: list[dict[str, Any]],
    *,
    target_category: str,
) -> tuple[olca_schema.ProductSystem, dict[str, Any]]:
    repair_errors = _repair_foreground_process_providers(
        client, inventory, target_category
    )
    if repair_errors:
        raise ValueError("; ".join(repair_errors))
    ref_process = source_data.get("refProcess") or {}
    ref_process_id = ref_process.get("@id") if isinstance(ref_process, dict) else None
    if not isinstance(ref_process_id, str):
        raise ValueError("ProductSystem requires refProcess for explicit linking")
    if _foreground_process_data(inventory, ref_process_id) is None:
        raise ValueError(f"refProcess {ref_process_id} not found in LCI inventory")

    expected_raw = source_data.get("expectedProcessIds") or []
    expected_ids = [
        process_id for process_id in expected_raw if isinstance(process_id, str)
    ]
    if not expected_ids:
        raise ValueError("ProductSystem expectedProcessIds must be non-empty")

    foreground_flow_ids = _foreground_flow_ids(inventory)
    process_refs: dict[str, olca_schema.Ref] = {}
    links: list[olca_schema.ProcessLink] = []
    ref_exchange: olca_schema.Exchange | None = None
    unlinked_inputs = _collect_unlinked_inputs(inventory, expected_ids)

    for item in inventory:
        if item["entity_type"] != "Process" or item["id"] not in set(expected_ids):
            continue
        process_refs[item["id"]] = olca_schema.Ref(id=item["id"], name=item["name"])
        saved_process = _read_saved_process(client, item["id"])
        for exchange in item["data"].get("exchanges", []):
            if not isinstance(exchange, dict):
                continue
            if exchange.get("isInput") is not True:
                if (
                    item["id"] == ref_process_id
                    and exchange.get("isQuantitativeReference") is True
                ):
                    flow = exchange.get("flow") or {}
                    flow_id = flow.get("@id")
                    saved_out = _match_saved_output_exchange(
                        saved_process,
                        process_id=item["id"],
                        flow_id=flow_id,
                        amount=exchange.get("amount", 1.0),
                    )
                    internal_id = getattr(saved_out, "internal_id", None)
                    if internal_id is None:
                        raise ValueError(
                            f"quantitative-reference on {item['id']} lacks internal_id"
                        )
                    ref_exchange = olca_schema.Exchange(
                        internal_id=internal_id,
                        flow=olca_schema.Ref(
                            id=flow_id,
                            name=flow.get("name"),
                        ),
                        is_input=False,
                        amount=exchange.get("amount", 1.0),
                        flow_property=getattr(saved_out, "flow_property", None),
                        unit=getattr(saved_out, "unit", None),
                    )
                continue
            if not _is_technosphere_input(exchange, foreground_flow_ids):
                continue
            flow = exchange.get("flow") or {}
            flow_id = flow.get("@id")
            provider = exchange.get("defaultProvider") or {}
            provider_id = provider.get("@id")
            if not isinstance(flow_id, str) or not flow_id:
                raise ValueError(f"technosphere input on {item['id']} lacks flow @id")
            if not isinstance(provider_id, str) or not provider_id:
                raise ValueError(
                    f"technosphere input flow {flow_id} on {item['id']} "
                    "requires defaultProvider"
                )
            amount = exchange.get("amount", 1.0)
            saved_in = _match_saved_input_exchange(
                saved_process,
                process_id=item["id"],
                flow_id=flow_id,
                provider_id=provider_id,
                amount=amount,
            )
            internal_id = getattr(saved_in, "internal_id", None)
            if internal_id is None:
                raise ValueError(
                    f"matched input on {item['id']} flow={flow_id} lacks internal_id"
                )
            if provider_id not in process_refs:
                process_refs[provider_id] = olca_schema.Ref(
                    id=provider_id,
                    name=provider.get("name"),
                )
            links.append(
                olca_schema.ProcessLink(
                    provider=olca_schema.Ref(id=provider_id),
                    process=olca_schema.Ref(id=item["id"]),
                    flow=olca_schema.Ref(id=flow_id, name=flow.get("name")),
                    exchange=olca_schema.ExchangeRef(internal_id=internal_id),
                )
            )

    if ref_exchange is None:
        raise ValueError("refProcess has no quantitative reference output exchange")

    provider_ids = {link.provider.id for link in links if link.provider and link.provider.id}
    provider_types = _provider_types_for_ids(client, provider_ids)

    entity.processes = list(process_refs.values())
    entity.process_links = links
    entity.ref_process = olca_schema.Ref(id=ref_process_id)
    entity.ref_exchange = ref_exchange
    if entity.target_amount is None and source_data.get("targetAmount") is not None:
        entity.target_amount = source_data["targetAmount"]
    if (
        entity.target_flow_property is None
        and getattr(ref_exchange, "flow_property", None) is not None
    ):
        entity.target_flow_property = ref_exchange.flow_property
    if entity.target_unit is None and getattr(ref_exchange, "unit", None) is not None:
        entity.target_unit = ref_exchange.unit
    meta = {
        "unlinked_inputs": unlinked_inputs,
        "provider_types": provider_types,
    }
    return entity, meta


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
    client: OpenLcaClient,
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
    provider_cache: dict[str, Any] = {}
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
            if provider_id not in provider_cache:
                provider_cache[provider_id] = client.get(
                    olca_schema.Process, provider_id
                )
            provider = provider_cache[provider_id]
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
        check["provider_content_hash"] = stable_hash(provider.to_dict())
        output_flow_ids = sorted(
            flow_id
            for exchange in list(getattr(provider, "exchanges", None) or [])
            if getattr(exchange, "is_input", None) is not True
            for flow_id in [getattr(getattr(exchange, "flow", None), "id", None)]
            if flow_id is not None
        )
        check["provider_unit"] = _provider_output_unit(provider, requirement["flow_id"])
        check["output_flow_count"] = len(output_flow_ids)
        check["output_flow_match"] = requirement["flow_id"] in output_flow_ids
        check["matched_flow_id"] = (
            requirement["flow_id"] if check["output_flow_match"] else None
        )
        check["diagnostic_flow_ids"] = (
            [] if check["output_flow_match"] else output_flow_ids[:10]
        )
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


# Mass transport unit group (openLCA "Units of mass*distance"), factor in kg*km.
_MASS_TRANSPORT_FACTORS = {
    "kg*km": 1.0,
    "t*km": 1000.0,
    "kt*km": 1_000_000.0,
    "g*km": 0.001,
    "kg*m": 0.001,
    "t*m": 1.0,
}


_UNIT_ALIASES = {"tkm": "t*km", "kgkm": "kg*km", "ton*km": "t*km", "tonne*km": "t*km"}


def _norm_unit(name: Any) -> str | None:
    if not isinstance(name, str) or not name.strip():
        return None
    text = name.strip().casefold()
    for sep in ("·", "⋅", "×", " x ", " ", "-"):
        text = text.replace(sep, "*" if sep not in {" "} else "")
    text = text.replace("**", "*")
    return _UNIT_ALIASES.get(text, text)


def _transport_unit_pass(
    inventory: list[dict[str, Any]],
    provider_checks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Reconcile foreground exchange units with mass-transport providers.

    For providers whose reference unit is in the mass*distance group (t*km ...),
    an LCI amount in another unit of that group (e.g. kg*km) is converted
    explicitly in the import payload and reported; an unknown or incompatible
    unit is an error. Amounts are never passed through silently.
    """
    units = {
        (c["provider_id"], c["flow_id"]): c.get("provider_unit")
        for c in provider_checks
        if c.get("provider_unit")
    }
    conversions: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in inventory:
        if item["entity_type"] != "Process":
            continue
        for index, exchange in enumerate(item["data"].get("exchanges", []), start=1):
            if not isinstance(exchange, dict) or exchange.get("isInput") is not True:
                continue
            provider = exchange.get("defaultProvider")
            flow = exchange.get("flow")
            if not isinstance(provider, dict) or not isinstance(flow, dict):
                continue
            target = units.get((provider.get("@id"), flow.get("@id")))
            if not target:
                continue
            p_unit = _norm_unit(target.get("name"))
            unit_ref = exchange.get("unit")
            raw_name = unit_ref.get("name") if isinstance(unit_ref, dict) else None
            l_unit = _norm_unit(raw_name)
            where = f"{item['path']}: exchange {index} ({flow.get('name') or flow.get('@id')})"
            p_transport = p_unit in _MASS_TRANSPORT_FACTORS
            l_transport = l_unit in _MASS_TRANSPORT_FACTORS
            if not p_transport:
                if l_transport:
                    errors.append(
                        f"{where}: unit {raw_name!r} is mass*distance but provider "
                        f"reference unit is {target.get('name')!r}"
                    )
                continue
            if l_unit is None:
                errors.append(
                    f"{where}: unit missing; provider {provider.get('@id')} is in "
                    f"mass transport unit group ({target.get('name')}); state the unit "
                    "explicitly (e.g. t*km)"
                )
                continue
            if not l_transport:
                errors.append(
                    f"{where}: unit {raw_name!r} incompatible with provider reference "
                    f"unit {target.get('name')!r} (mass transport)"
                )
                continue
            if l_unit == p_unit:
                continue
            amount = exchange.get("amount")
            if not isinstance(amount, (int, float)) or isinstance(amount, bool):
                errors.append(f"{where}: amount must be numeric for unit conversion")
                continue
            factor = _MASS_TRANSPORT_FACTORS[l_unit] / _MASS_TRANSPORT_FACTORS[p_unit]
            converted = amount * factor
            exchange["amount"] = converted
            new_ref: dict[str, Any] = {"@type": "Unit", "name": target.get("name")}
            if target.get("id"):
                new_ref["@id"] = target["id"]
            exchange["unit"] = new_ref
            conversions.append(
                {
                    "path": item["path"],
                    "process_id": item["id"],
                    "exchange": index,
                    "flow_id": flow.get("@id"),
                    "provider_id": provider.get("@id"),
                    "from_unit": raw_name,
                    "to_unit": target.get("name"),
                    "factor": factor,
                    "original_amount": amount,
                    "converted_amount": converted,
                    "note": (
                        f"{where}: {amount} {raw_name} converted to "
                        f"{converted} {target.get('name')} (x{factor:g}) to match "
                        "provider reference unit"
                    ),
                }
            )
    return conversions, errors


def _database_snapshot(
    client: OpenLcaClient,
    target_category: str,
) -> tuple[list[dict[str, Any]], list[tuple[str, OlcaDescriptor]]]:
    all_records: list[dict[str, Any]] = []
    target_descriptors: list[tuple[str, OlcaDescriptor]] = []
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


def _existing_outside_project_errors(
    inventory: list[dict[str, Any]],
    database_records: list[dict[str, Any]],
    target_category: str,
) -> list[str]:
    """Reject import files whose @id already belongs to a non-project entity."""
    by_key = {
        (str(record.get("entity_type")), str(record.get("id"))): record
        for record in database_records
        if record.get("id")
    }
    errors: list[str] = []
    for item in inventory:
        record = by_key.get((str(item.get("entity_type")), str(item.get("id"))))
        if record is None:
            continue
        category = record.get("category")
        category_text = category if isinstance(category, str) else None
        if not category_outside_project(category_text, target_category):
            continue
        errors.append(
            f"{item['path']}: @id {item['id']} 已存在且不在本项目分类，"
            "只能在交换里引用，不能作为导入文件"
        )
    return errors


def _outside_project_import_refusal(
    client: OpenLcaClient,
    item: dict[str, Any],
    target_category: str,
) -> str | None:
    """Second door: skip put when this @id already exists outside the project."""
    model_type = ENTITY_TYPES.get(str(item.get("entity_type")))
    entity_id = str(item.get("id") or "")
    if model_type is None or not entity_id:
        return None
    try:
        existing = client.get(model_type, entity_id)
    except Exception as exc:
        # Fail closed: if we cannot verify, never overwrite a possibly foreign entity.
        return (
            f"无法核实 @id {entity_id} 是否已存在（查询出错: {exc}），"
            "为避免覆盖数据库已有数据，拒绝写入"
        )
    if existing is None:
        return None
    category = getattr(existing, "category", None)
    category_text = category if isinstance(category, str) else None
    if not category_outside_project(category_text, target_category):
        return None
    return (
        f"@id {entity_id} 已存在且不在本项目分类，"
        "只能在交换里引用，不能作为导入文件"
    )


def _inspect_import(
    host: str,
    port: int,
    lci_dir: str | Path,
    target_category: str,
    database_name: str | None = None,
    client: OpenLcaClient | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[tuple[str, OlcaDescriptor]]]:
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
                "schema": "openlca/import-preflight",
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
        raise RuntimeError(
            f"Failed to inspect active openLCA database at {endpoint}: {exc}"
        ) from exc

    background_process_ids = {
        str(record["id"])
        for record in database_records
        if record.get("entity_type") == "Process" and record.get("id")
    }
    reference_errors = _preflight_foreground_provider_reference_errors(
        inventory,
        background_process_ids=background_process_ids,
    )

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
    overwrite_scope.sort(key=lambda item: (item["entity_type"], str(item["id"] or "")))
    provider_checks, provider_errors = _provider_checks(
        ipc_client,
        inventory,
        database_records,
    )
    if owns_client:
        close_ipc_client(ipc_client)
    unit_conversions, unit_errors = _transport_unit_pass(inventory, provider_checks)
    identity_errors = _existing_outside_project_errors(
        inventory, database_records, category
    )
    provider_errors = [
        *provider_errors,
        *unit_errors,
        *reference_errors,
        *identity_errors,
    ]
    unlinked_warnings: list[str] = []
    for item in inventory:
        if item["entity_type"] != "ProductSystem":
            continue
        expected = item["data"].get("expectedProcessIds") or []
        expected_ids = [
            process_id for process_id in expected if isinstance(process_id, str)
        ]
        for entry in _collect_unlinked_inputs(inventory, expected_ids):
            unlinked_warnings.append(
                f"{entry['path']}: exchanges[{entry['exchange_index']}] "
                f"elementary input flow={entry.get('flow_id')} has no defaultProvider"
            )
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
        "unit_conversions": unit_conversions,
    }
    preflight_hash = stable_hash(hash_payload)
    ok = not provider_errors
    return (
        {
            "schema": "openlca/import-preflight",
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
            "unit_conversions": unit_conversions,
            "warnings": [
                *[c["note"] for c in unit_conversions],
                *unlinked_warnings,
            ],
            "preflight_hash": preflight_hash,
            "timestamp": utc_now(),
        },
        inventory,
        target_descriptors,
    )


def _public_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    hidden = {
        "preflight_hash",
        "lci_fingerprint",
        "target_scope_fingerprint",
        "background_provider_fingerprint",
        "database_fingerprint",
    }
    public = {key: value for key, value in preflight.items() if key not in hidden}
    planned = []
    for item in public.get("planned_entities") or []:
        copy = dict(item)
        copy.pop("sha256", None)
        planned.append(copy)
    public["planned_entities"] = planned
    return public


def _apply_generated_product_system_fields(
    entity: olca_schema.ProductSystem,
    generated: olca_schema.ProductSystem,
) -> None:
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


def find_uncertain_leftover_entities(
    client: OpenLcaClient,
    inventory: list[dict[str, Any]],
    target_category: str,
) -> list[dict[str, Any]]:
    """When IPC state is uncertain, report DB entities that match planned import ids."""
    leftovers: list[dict[str, Any]] = []
    for item in inventory:
        entity_type = item.get("entity_type")
        model_type = ENTITY_TYPES.get(str(entity_type))
        entity_id = str(item.get("id") or "")
        if model_type is None or not entity_id:
            continue
        try:
            existing = client.get(model_type, entity_id)
        except Exception:
            continue
        if existing is None:
            continue
        category = getattr(existing, "category", None)
        if category and category != target_category and not str(category).startswith(
            f"{target_category}/"
        ):
            continue
        leftovers.append(
            {
                "path": item.get("path"),
                "entity_type": entity_type,
                "id": entity_id,
                "name": item.get("name") or getattr(existing, "name", None),
                "database_category": category,
            }
        )
    return leftovers


def _put_product_system_explicit(
    client: OpenLcaClient,
    entity: olca_schema.ProductSystem,
    source_data: dict[str, Any],
    inventory: list[dict[str, Any]],
    *,
    target_category: str,
) -> tuple[object, dict[str, Any]]:
    """Save a Product System with host-built links (no data/create/system)."""
    if source_data.get("preferDefaultProviders") is not True:
        raise ValueError("ProductSystem preferDefaultProviders must be true")
    built, build_meta = _build_explicit_product_system(
        client, entity, source_data, inventory, target_category=target_category
    )
    built.category = target_category
    ps_read = product_system_read_sec()
    with ipc_read_scope(ps_read):
        reference = client.put(built)
    if reference is None:
        raise RuntimeError("IPC Server did not return an entity reference")
    with ipc_read_scope(ps_read):
        read_back = client.get(olca_schema.ProductSystem, str(getattr(built, "id", "")))
    if read_back is None:
        raise RuntimeError(
            f"IPC Server could not read back ProductSystem {getattr(built, 'id', None)}"
        )
    meta = {
        "linking_mode_applied": "explicit",
        "linking_mode_declared": "explicit",
        **build_meta,
    }
    return reference, meta


def _explicit_link_provider_ids(
    inventory: list[dict[str, Any]], source_data: dict[str, Any]
) -> set[str]:
    expected_ids = [
        process_id
        for process_id in (source_data.get("expectedProcessIds") or [])
        if isinstance(process_id, str)
    ]
    foreground_flow_ids = _foreground_flow_ids(inventory)
    provider_ids: set[str] = set()
    for item in inventory:
        if item["entity_type"] != "Process" or item["id"] not in set(expected_ids):
            continue
        for exchange in item["data"].get("exchanges", []):
            if not isinstance(exchange, dict) or not _is_technosphere_input(
                exchange, foreground_flow_ids
            ):
                continue
            provider_id = _exchange_provider_id(exchange)
            if provider_id:
                provider_ids.add(provider_id)
    return provider_ids


def _explicit_link_blocked_by_unit_process_providers(
    client: OpenLcaClient,
    inventory: list[dict[str, Any]],
    source_data: dict[str, Any],
) -> tuple[bool, list[str], dict[str, str | None]]:
    provider_ids = _explicit_link_provider_ids(inventory, source_data)
    if not provider_ids:
        return False, [], {}
    provider_types = _provider_types_for_ids(client, provider_ids)
    unit_ids = _unit_process_providers(provider_types)
    return bool(unit_ids), unit_ids, provider_types


def _put_product_system(
    client: OpenLcaClient,
    entity: olca_schema.ProductSystem,
    source_data: dict[str, Any],
    *,
    inventory: list[dict[str, Any]] | None = None,
    target_category: str = "",
) -> tuple[object, dict[str, Any]]:
    """Create a Product System (explicit put or openLCA auto-linking API)."""
    linking_mode = source_data.get("linkingMode")
    if linking_mode not in {"auto", "explicit"}:
        raise ValueError("ProductSystem linkingMode must be 'auto' or 'explicit'")
    if source_data.get("preferDefaultProviders") is not True:
        raise ValueError("ProductSystem preferDefaultProviders must be true")

    ref_process = source_data.get("refProcess") or {}
    ref_process_id = ref_process.get("@id") if isinstance(ref_process, dict) else None
    expected_ids = [
        process_id
        for process_id in (source_data.get("expectedProcessIds") or [])
        if isinstance(process_id, str)
    ]
    use_explicit = linking_mode == "explicit"
    if (
        linking_mode == "auto"
        and inventory is not None
        and expected_ids
        and _foreground_has_technosphere_inputs(inventory, expected_ids)
        and _all_foreground_technosphere_have_providers(inventory, expected_ids)
    ):
        use_explicit = True

    unit_block_note: str | None = None
    if use_explicit and inventory is not None:
        blocked, unit_ids, provider_types = _explicit_link_blocked_by_unit_process_providers(
            client, inventory, source_data
        )
        if blocked:
            if linking_mode == "explicit":
                raise ValueError(
                    "explicit ProductSystem linking cannot use UNIT_PROCESS providers "
                    f"(truncates supply chain): {unit_ids}"
                )
            use_explicit = False
            unit_block_note = (
                "auto preferred explicit host linking but UNIT_PROCESS providers "
                f"would truncate the supply chain: {unit_ids}; "
                f"provider_types={provider_types}"
            )

    category = target_category.strip()
    if category:
        entity.category = category

    if use_explicit:
        if inventory is None:
            raise ValueError("explicit ProductSystem import requires LCI inventory")
        if not category:
            raise ValueError("ProductSystem import requires target_category")
        reference, meta = _put_product_system_explicit(
            client,
            entity,
            source_data,
            inventory,
            target_category=category,
        )
        declared = str(source_data.get("linkingMode") or "auto")
        meta["linking_mode_declared"] = declared
        if declared == "auto":
            meta["linking_mode_applied"] = "explicit"
            meta["linking_mode_note"] = (
                "auto requested but all technosphere inputs have defaultProvider; "
                "used explicit host linking to avoid data/create/system hang risk"
            )
        return reference, meta

    ref_process = getattr(entity, "ref_process", None)
    if ref_process is None or not getattr(ref_process, "id", None):
        raise ValueError("ProductSystem requires refProcess for automatic linking")

    declared_id = getattr(entity, "id", None)
    if not isinstance(declared_id, str) or not declared_id.strip():
        raise ValueError("ProductSystem requires a declared UUID")

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

    generated_ref: object | None = None
    generated_id: str | None = None
    generated: olca_schema.ProductSystem | None = None

    # No automatic retry: a read timeout on create/readback propagates at once so the
    # caller's unresponsive probe can mark openLCA down instead of waiting again.
    ps_read = product_system_read_sec()
    with ipc_read_scope(ps_read):
        generated_ref = client.create_product_system(ref_process, config)
    generated_id = getattr(generated_ref, "id", None)
    if not generated_id:
        raise RuntimeError("IPC Server did not create an auto-linked ProductSystem")
    with ipc_read_scope(ps_read):
        generated = client.get(olca_schema.ProductSystem, generated_id)
    if generated is None:
        raise RuntimeError(
            f"IPC Server could not read generated ProductSystem {generated_id}"
        )

    assert generated is not None
    _apply_generated_product_system_fields(entity, generated)
    if category:
        entity.category = category

    try:
        with ipc_read_scope(ps_read):
            reference = client.put(entity)
        if reference is None:
            raise RuntimeError("IPC Server did not return an entity reference")
    except Exception as exc:
        if generated_ref is not None and generated_id != declared_id:
            try:
                client.delete(generated_ref)
            except Exception as cleanup_exc:
                if category and generated is not None:
                    try:
                        generated.category = category
                        client.put(generated)
                    except Exception:
                        pass
                raise RuntimeError(
                    f"{exc}; additionally could not delete temporary ProductSystem "
                    f"{generated_id}: {cleanup_exc}"
                ) from exc
        raise

    if generated_ref is not None and generated_id != getattr(reference, "id", None):
        try:
            client.delete(generated_ref)
        except Exception as exc:
            raise RuntimeError(
                f"saved ProductSystem but could not delete temporary system "
                f"{generated_id}: {exc}"
            ) from exc

    auto_meta: dict[str, Any] = {
        "linking_mode_applied": "auto",
        "linking_mode_declared": linking_mode,
    }
    if unit_block_note:
        auto_meta["linking_mode_note"] = unit_block_note
    return reference, auto_meta


def _execute_import(
    client: OpenLcaClient,
    inventory: list[dict[str, Any]],
    target_descriptors: list[tuple[str, OlcaDescriptor]],
    target_category: str,
    emit: Callable[[str], None] | None = None,
    on_progress: (
        Callable[[list[dict[str, Any]], int, int, int, list[str]], None] | None
    ) = None,
    *,
    host: str | None = None,
    port: int | None = None,
    resume: bool = False,
    entity_plan: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], int, int, int, list[str]]:
    records: list[dict[str, Any]] = []
    imported = 0
    failed = 0
    deleted = 0
    errors: list[str] = []
    output = emit or (lambda _message: None)
    plan = list(entity_plan or build_entity_plan(inventory))
    plan_lookup = _plan_by_id(plan)
    providers_repaired = False

    if not resume:

        def progress(*extra: object) -> None:
            if on_progress is not None:
                on_progress(records, imported, failed, deleted, errors)

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
                    output(
                        f"  [已删除] {entity_type}: {entity_name} (UUID: {entity_id})"
                    )
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
                    if transport_failed and host is not None and port is not None:
                        on_ipc_transport_failure(
                            host,
                            port,
                            exc,
                            operation="delete",
                            entity={
                                "path": "openlca://active-database",
                                "entity_type": entity_type,
                                "id": entity_id,
                                "name": entity_name,
                            },
                        )
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
                progress()
                if transport_failed:
                    return records, imported, failed, deleted, errors

    for item in inventory:
        plan_entry = plan_lookup.get(item["id"])
        if plan_entry and plan_entry.get("status") == "done":
            output(f"跳过已完成实体: {item['path']} ({item['id']})")
            if on_progress is not None:
                on_progress(records, imported, failed, deleted, errors)
            continue
        if item["entity_type"] == "ProductSystem" and not providers_repaired:
            repair_errors = _repair_foreground_process_providers(
                client, inventory, target_category
            )
            providers_repaired = True
            if repair_errors:
                failed += len(repair_errors)
                errors.extend(repair_errors)
                for message in repair_errors:
                    output(f"[错误] {message}")
                if on_progress is not None:
                    on_progress(records, imported, failed, deleted, errors)
                return records, imported, failed, deleted, errors

        output(f"正在处理文件: {item['path']}...")
        transport_failed = False
        linking_meta: dict[str, Any] = {}
        try:
            refusal = _outside_project_import_refusal(client, item, target_category)
            if refusal is not None:
                raise RuntimeError(refusal)
            entity = _deserialize_entity(item, target_category)
            if isinstance(entity, olca_schema.ProductSystem):
                reference, linking_meta = _put_product_system(
                    client,
                    entity,
                    item["data"],
                    inventory=inventory,
                    target_category=target_category,
                )
            else:
                reference = client.put(entity)
            if reference is None:
                raise RuntimeError("IPC Server did not return an entity reference")
            imported += 1
            returned_id = getattr(reference, "id", None) or item["id"]
            if plan_entry is not None:
                plan_entry["status"] = "done"
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
                    "content_hash": item.get("sha256", ""),
                    "entity_status": "done",
                    "action": "create_or_update",
                    "status": "success",
                    "error": None,
                    **linking_meta,
                }
            )
        except Exception as exc:
            failed += 1
            transport_failed = is_transport_error(exc)
            entity_status = "uncertain" if transport_failed else "failed"
            if plan_entry is not None:
                plan_entry["status"] = entity_status
            message = f"import {item['path']}: {exc}"
            errors.append(message)
            output(f"[错误] {message}")
            if transport_failed and host is not None and port is not None:
                on_ipc_transport_failure(
                    host,
                    port,
                    exc,
                    operation="import",
                    entity={
                        "path": item["path"],
                        "entity_type": item["entity_type"],
                        "id": item["id"],
                        "name": item["name"],
                    },
                )
            records.append(
                {
                    "path": item["path"],
                    "entity_type": item["entity_type"],
                    "id": item["id"],
                    "name": item["name"],
                    "content_hash": item.get("sha256", ""),
                    "entity_status": entity_status,
                    "action": "create_or_update",
                    "status": "failed",
                    "error": str(exc),
                }
            )
        if on_progress is not None:
            on_progress(records, imported, failed, deleted, errors)
        if transport_failed:
            return records, imported, failed, deleted, errors
    if not providers_repaired and any(
        item["entity_type"] == "Process" for item in inventory
    ):
        repair_errors = _repair_foreground_process_providers(
            client, inventory, target_category
        )
        if repair_errors:
            failed += len(repair_errors)
            errors.extend(repair_errors)
            for message in repair_errors:
                output(f"[错误] {message}")
    return records, imported, failed, deleted, errors
