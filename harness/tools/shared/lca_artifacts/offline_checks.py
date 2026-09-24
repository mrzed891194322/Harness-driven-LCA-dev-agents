"""Offline LCA checks. All data and paths are explicit; no host context."""

from __future__ import annotations

import json
import math
from pathlib import Path

from harness.tools.shared.control_openlca.workflow import validate_lci_directory


def read_items(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise ValueError(f"{path.name}: expected items array")
    if not value["items"] or any(not isinstance(item, dict) for item in value["items"]):
        raise ValueError(f"{path.name}: nonempty object rows required")
    return value["items"]


def inventory_errors(rows: list[dict], declared: set[str]) -> list[str]:
    errors = []
    ids = [r.get("item_id") for r in rows]
    if any(not isinstance(i, str) or not i for i in ids) or len(
        set(map(str, ids))
    ) != len(ids):
        errors.append("item_id must be unique nonempty strings")
    required = {
        "item_id",
        "name",
        "quantity",
        "unit",
        "process",
        "transport",
        "geography",
        "source_locations",
        "extraction_status",
    }
    for row in rows:
        label = row.get("item_id", "unknown")
        if required - row.keys():
            errors.append(f"{label}: missing {sorted(required - row.keys())}")
        if row.get("extraction_status") not in {"extracted", "partial", "unreadable"}:
            errors.append(f"{label}: invalid extraction_status")
        quantity = row.get("quantity")
        if quantity is not None and (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or not math.isfinite(quantity)
        ):
            errors.append(
                f"{label}: quantity must be a finite number or null for an explicit gap"
            )
        if row.get("extraction_status") == "extracted" and quantity is None:
            errors.append(f"{label}: extracted row needs a quantity")
        for field in ("name", "unit", "process"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"{label}: {field} must be a nonempty string")
        sources = row.get("source_locations")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{label}: missing source locations")
            continue
        for source in sources:
            if (
                not isinstance(source, str)
                or "#" not in source
                or not source.split("#", 1)[1]
            ):
                errors.append(
                    f"{label}: source requires path/document ID plus #locator"
                )
                continue
            source_id = source.split("#", 1)[0]
            candidates = {source_id, source_id.replace("\\", "/")}
            if candidates & declared:
                continue
            errors.append(f"{label}: undeclared source reference: {source}")
    return errors


def mapping_errors(
    bom: list[dict],
    mapping: list[dict],
    lci_dir: Path,
    provider_pairs: set[tuple[str, str]],
) -> list[str]:
    errors = []
    ids = [item.get("item_id") for item in mapping]
    if set(map(str, ids)) != {str(item.get("item_id")) for item in bom} or len(
        ids
    ) != len(set(map(str, ids))):
        errors.append("BOM/mapping item_id coverage mismatch or duplicate")
    validation = validate_lci_directory(lci_dir)
    errors.extend(validation["errors"])
    if validation["errors"]:
        return errors
    processes = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (lci_dir / "processes").glob("*.json")
        if not path.is_symlink()
    ]
    foreground = {process["@id"] for process in processes}
    for process in processes:
        for exchange in process.get("exchanges", []):
            provider = (exchange.get("defaultProvider") or {}).get("@id")
            flow = (exchange.get("flow") or {}).get("@id")
            if (
                provider
                and provider not in foreground
                and (provider, flow) not in provider_pairs
            ):
                errors.append(f"formal provider evidence missing: {provider}/{flow}")
    return errors
