"""Offline checks and dependency invalidation, independent of stage advancement."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from harness.tools.control_openlca.utils.guard import file_lock
from harness.tools.control_openlca.utils.workflow import (
    _write_json_atomic,
    sha256_file,
    stable_hash,
    utc_now,
    validate_lci_directory,
)

CHECKER_VERSION = "2.0"
PROFILES = {
    "inventory": "02-inventory-extraction",
    "mapping": "03-dataset-mapping",
    "report": "04-openlca-reporting",
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def upstream_files(ctx):
    paths = [
        ctx.workspace / "inputs" / "plan.md",
        ctx.workspace / "outputs" / "inventory" / "extracted-bom.json",
        ctx.workspace / "outputs" / "inventory" / "process-mapping.json",
    ]
    if (ctx.workspace / "inputs" / "revise.md").exists():
        paths.append(ctx.workspace / "inputs" / "revise.md")
    for root in (
        ctx.workspace / "outputs" / "LCI",
        ctx.project / "harness" / "knowledge",
    ):
        if root.exists():
            paths.extend(p for p in sorted(root.rglob("*")) if p.is_file())
    return paths


def fingerprints(paths):
    return {
        str(p.resolve()): sha256_file(p) if p.is_file() else "missing" for p in paths
    }


def model_fingerprint(ctx):
    return stable_hash(fingerprints(upstream_files(ctx)))


def calculation_path(ctx):
    return ctx.safe(ctx.workspace / "outputs" / "reports" / "calculation-plan.json")


def calculation_fingerprint(ctx):
    path = calculation_path(ctx)
    return sha256_file(path) if path.is_file() else "missing"


def record_acceptance(ctx):
    """Persist the reviewer's decision; does not judge or advance the workflow."""
    with file_lock(ctx.safe(ctx.memory / "manifest.lock")):
        value = ctx.load_manifest()
        value["accepted"][ctx.stage] = {
            "model_fingerprint": model_fingerprint(ctx),
            "at": utc_now(),
            "attempt": ctx.attempt,
        }
        _write_json_atomic(ctx.manifest, value)


def require_approved_model(ctx, *, allow_reviewer=False):
    if ctx.stage == "standalone":
        return
    if ctx.stage != PROFILES["report"] or (
        ctx.role == "reviewer" and not allow_reviewer
    ):
        raise ValueError("only stage 04 writer can import or calculate")
    accepted = ctx.load_manifest()["accepted"].get(PROFILES["mapping"])
    if not accepted or accepted["model_fingerprint"] != model_fingerprint(ctx):
        raise ValueError("approved model missing or stale; upstream review required")


def require_calculation_plan(ctx, arguments):
    if ctx.stage == "standalone":
        return
    plans = load(calculation_path(ctx)).get("calculations", [])
    matching = [
        p
        for p in plans
        if p.get("product_system") == arguments["product_system"]
        and p.get("impact_method") == arguments["impact_method"]
    ]
    if len(matching) != 1:
        raise ValueError(
            "calculation target/method must occur once in calculation-plan.json"
        )
    for key, default in {
        "amount": 1.0,
        "allocation": None,
        "regionalized": False,
        "costs": False,
        "parameters": {},
    }.items():
        actual = arguments.get(key, default)
        if key == "parameters" and actual is None:
            actual = {}
        if matching[0].get(key, default) != actual:
            raise ValueError(f"calculation request differs from plan: {key}")


def require_import_directory(ctx, directory):
    if ctx.stage == "standalone":
        return
    canonical = ctx.workspace / "outputs" / "LCI"

    def contents(root):
        return {
            str(p.relative_to(root)): sha256_file(p)
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    if contents(Path(directory)) != contents(canonical):
        raise ValueError("import directory differs from the reviewed canonical LCI")


def selected_calls(ctx, tools):
    """Latest evidence per tool and calculation target, always within this run."""
    selected = {}
    for call in ctx.load_manifest()["calls"]:
        call = {**call, "tool": call.get("evidence_tool", call["tool"])}
        if call["tool"] not in tools:
            continue
        args = call.get("arguments", {})
        key = (
            call["tool"],
            args.get("product_system", ""),
            args.get("impact_method", ""),
        )
        selected[key] = call
    return list(selected.values())


def evidence(ctx):
    calls = selected_calls(
        ctx, {"import_lci", "get_model_graph", "calculate_product_system"}
    )
    result = []
    for call in calls:
        raw = load(ctx.resolve_ref(call["artifact"]))
        if call.get("model_fingerprint") != model_fingerprint(ctx):
            raise ValueError("raw evidence is stale relative to approved inputs")
        if call["tool"] == "calculate_product_system":
            plans = load(calculation_path(ctx)).get("calculations", [])
            matching = [
                p
                for p in plans
                if p["product_system"] == call["arguments"].get("product_system")
                and p["impact_method"] == call["arguments"].get("impact_method")
            ]
            if not matching:
                continue
            for key, default in {
                "amount": 1.0,
                "allocation": None,
                "regionalized": False,
                "costs": False,
                "parameters": {},
            }.items():
                if raw.get("calculation_setup", {}).get(key, default) != matching[
                    0
                ].get(key, default):
                    raise ValueError(
                        f"calculation settings changed: {call['arguments'].get('product_system')}/{key}"
                    )
        result.append((call, raw))
    return result


def report_evidence_errors(ctx):
    require_approved_model(ctx, allow_reviewer=True)
    errors = []
    data = evidence(ctx)
    systems = [
        load(p)["@id"]
        for p in sorted(
            (ctx.workspace / "outputs" / "LCI" / "product_systems").glob("*.json")
        )
    ]
    plans = load(calculation_path(ctx)).get("calculations", [])
    if not plans or not systems:
        errors.append("calculation plan and Product Systems must be nonempty")
    if len({(p["product_system"], p["impact_method"]) for p in plans}) != len(plans):
        errors.append("duplicate calculation plan system/method pair")
    if set(p["product_system"] for p in plans) != set(systems):
        errors.append("calculation plan must cover every declared Product System UUID")
    imports = [(c, r) for c, r in data if c["tool"] == "import_lci"]
    if (
        not imports
        or imports[-1][1].get("status") != "success"
        or imports[-1][0]["status"] != "success"
    ):
        errors.append("successful import evidence missing")
    elif imports:
        raw = imports[-1][1]
        if (
            not raw.get("operation_id")
            or not raw.get("request_id")
            or raw.get("identity", {}).get("run_id") != ctx.run_id
        ):
            errors.append("import receipt identity missing or from another run")
        if raw.get("success_count", 0) <= 0 or raw.get("failed_count", 0) != 0:
            errors.append(
                "import receipt has no successful entities or contains failures"
            )
    for system in systems:
        graphs = [
            (c, r)
            for c, r in data
            if c["tool"] == "get_model_graph"
            and c["arguments"].get("product_system") == system
        ]
        if not graphs:
            errors.append(f"model graph missing: {system}")
        for call, raw in graphs:
            if (
                call["status"] != "success"
                or raw.get("status") != "success"
                or not raw.get("nodes")
                or any(
                    raw.get(k)
                    for k in (
                        "broken_links",
                        "disconnected_nodes",
                        "missing_expected_nodes",
                    )
                )
            ):
                errors.append(f"invalid graph: {system}")
            if raw.get("product_system", {}).get("id") != system:
                errors.append(f"graph target mismatch: {system}")
    for plan in plans:
        calculations = [
            (c, r)
            for c, r in data
            if c["tool"] == "calculate_product_system"
            and c["arguments"].get("product_system") == plan["product_system"]
            and c["arguments"].get("impact_method") == plan["impact_method"]
        ]
        if not calculations:
            errors.append(f"calculation missing: {plan['product_system']}")
        for call, raw in calculations:
            if (
                call["status"] != "success"
                or raw.get("status") != "success"
                or not raw.get("impact_categories")
                or raw.get("resource_released") is not True
            ):
                errors.append("failed, empty or unreleased calculation")
            if (
                raw.get("product_system", {}).get("id") != plan["product_system"]
                or raw.get("impact_method", {}).get("id") != plan["impact_method"]
            ):
                errors.append("calculation result target/method does not match plan")
            for key, default in {
                "amount": 1.0,
                "allocation": None,
                "regionalized": False,
                "costs": False,
                "parameters": {},
            }.items():
                if raw.get("calculation_setup", {}).get(key, default) != plan.get(
                    key, default
                ):
                    errors.append(f"calculation setting mismatch: {key}")
    return errors


def reuse_status(ctx):
    if ctx.attempt < 2:
        return {
            "eligible": False,
            "rework_scope": "none",
            "errors": [],
            "changes": ["first attempt requires full execution"],
        }
    previous_calculations = selected_calls(ctx, {"calculate_product_system"})
    settings_changed = calculation_fingerprint(ctx) != "missing" and any(
        c.get("calculation_fingerprint")
        not in {None, "missing", calculation_fingerprint(ctx)}
        for c in previous_calculations
    )
    repair_scope = "calculation_changed" if settings_changed else "none"
    try:
        require_approved_model(ctx, allow_reviewer=True)
        errors = report_evidence_errors(ctx)
        return {
            "eligible": not errors,
            "rework_scope": "report_only" if not errors else repair_scope,
            "errors": [],
            "changes": errors,
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Upstream changes are not a license to re-import within stage 04.
        accepted = ctx.load_manifest()["accepted"].get(PROFILES["mapping"], {})
        unchanged = accepted.get("model_fingerprint") == model_fingerprint(ctx)
        return {
            "eligible": False,
            "rework_scope": repair_scope if unchanged else "model_changed",
            "errors": [],
            "changes": [str(exc)],
        }


def _items(path):
    value = load(path)
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise ValueError(f"{path.name}: expected items array")
    if not value["items"] or any(not isinstance(i, dict) for i in value["items"]):
        raise ValueError(f"{path.name}: nonempty object rows required")
    return value["items"]


def inventory_errors(ctx):
    rows = _items(ctx.workspace / "outputs" / "inventory" / "extracted-bom.json")
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
            elif "://" not in source:
                path = (ctx.project / source.split("#", 1)[0]).resolve()
                if not path.is_file():
                    errors.append(f"{label}: source missing: {source}")
    return errors


def mapping_errors(ctx):
    bom = _items(ctx.workspace / "outputs" / "inventory" / "extracted-bom.json")
    mapping = _items(ctx.workspace / "outputs" / "inventory" / "process-mapping.json")
    errors = []
    ids = [i.get("item_id") for i in mapping]
    if set(map(str, ids)) != {str(i.get("item_id")) for i in bom} or len(ids) != len(
        set(map(str, ids))
    ):
        errors.append("BOM/mapping item_id coverage mismatch or duplicate")
    validation = validate_lci_directory(ctx.workspace / "outputs" / "LCI")
    errors.extend(validation["errors"])
    # Preflight and exact-pair batch checks are accepted formal provider evidence.
    found = set()
    for call in ctx.load_manifest()["calls"]:
        if call["tool"] not in {"preflight_import_lci", "validate_providers_batch"}:
            continue
        if call.get("model_fingerprint") != model_fingerprint(ctx):
            continue
        raw = load(ctx.resolve_ref(call["artifact"]))
        if call["status"] != "success":
            if call["tool"] == "preflight_import_lci":
                found.clear()
            else:
                for item in call.get("arguments", {}).get("requirements", []):
                    found.discard((item.get("process_id"), item.get("flow_id")))
        for check in raw.get("checks", raw.get("background_provider_checks", [])):
            pair = (
                check.get("process_id", check.get("provider_id")),
                check.get("flow_id"),
            )
            found.discard(pair)
            if check.get("exists") and check.get("output_flow_match"):
                found.add(pair)
    # Check actual external exchanges, rather than assuming every BOM row is a background flow.
    root = ctx.workspace / "outputs" / "LCI"
    processes = [load(p) for p in (root / "processes").glob("*.json")]
    foreground = {p["@id"] for p in processes}
    for process in processes:
        for exchange in process.get("exchanges", []):
            provider = (exchange.get("defaultProvider") or {}).get("@id")
            flow = (exchange.get("flow") or {}).get("@id")
            if (
                provider
                and provider not in foreground
                and (provider, flow) not in found
            ):
                errors.append(f"formal provider evidence missing: {provider}/{flow}")
    return errors


def dependencies(ctx, profile):
    paths = upstream_files(ctx)
    if profile == "inventory":
        paths = [
            p
            for p in paths
            if p.name != "process-mapping.json"
            and ctx.workspace / "outputs" / "LCI" not in p.parents
        ]
    if profile == "report":
        paths += [
            calculation_path(ctx),
            ctx.workspace / "outputs" / "reports" / "lca_report.md",
        ]
    tools = {
        "inventory": set(),
        "mapping": {"preflight_import_lci", "validate_providers_batch"},
        "report": {"import_lci", "get_model_graph", "calculate_product_system"},
    }[profile]
    refs = [
        call["artifact"]
        for call in ctx.load_manifest()["calls"]
        if call.get("evidence_tool", call["tool"]) in tools
        and call["stage"] == ctx.stage
    ]
    paths += [ctx.safe(ctx.workspace / ref["path"]) for ref in refs]
    return {"files": fingerprints(paths), "evidence_refs": refs}


def check_path(ctx, profile):
    if profile not in PROFILES:
        raise ValueError("unknown check profile")
    return ctx.safe(ctx.memory / "checks" / f"{profile}.json")


def validation_state_for_run(ctx, profile):
    return validation_state(ctx, profile)


def validation_state(ctx, profile):
    path = check_path(ctx, profile)
    if not path.exists():
        return {
            "check_id": profile,
            "checker_version": CHECKER_VERSION,
            "status": "not_run",
        }
    record = load(path)
    if record.get("checker_version") != CHECKER_VERSION or record.get(
        "inputs"
    ) != dependencies(ctx, profile):
        record = {**record, "status": "stale"}
        _write_json_atomic(path, record)
    return record


def validate(ctx, profile):
    if profile not in PROFILES or ctx.stage != PROFILES[profile]:
        raise ValueError("check profile does not belong to current stage")
    return validate_for_run(ctx, profile)


def validate_for_run(ctx, profile):
    if profile not in PROFILES:
        raise ValueError("unknown check profile")
    errors, warnings = [], []
    try:
        if profile == "inventory":
            errors = inventory_errors(ctx)
        elif profile == "mapping":
            errors = mapping_errors(ctx)
        else:
            from .report import language_hints, report_table_errors

            errors = report_evidence_errors(ctx) + report_table_errors(ctx)
            warnings.extend(language_hints(ctx))
            report = (
                ctx.workspace / "outputs" / "reports" / "lca_report.md"
            ).read_text(encoding="utf-8")
            if not re.search(r"[\u4e00-\u9fff]", report):
                warnings.append(
                    "report has no Chinese text; reviewer must assess explanation language"
                )
        inputs = dependencies(ctx, profile)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
        inputs = dependencies(ctx, profile)
    record = {
        "check_id": profile,
        "checker_version": CHECKER_VERSION,
        "status": "failed" if errors else "passed",
        "inputs": inputs,
        "executed_at": utc_now(),
        "summary": f"{profile}: {len(errors)} issue(s)",
        "errors": errors,
        "warnings": warnings,
    }
    path = check_path(ctx, profile)
    _write_json_atomic(path, record)
    history = ctx.safe(
        ctx.memory
        / "checks"
        / "history"
        / f"{profile}-{ctx.attempt}-{stable_hash(record)[:16]}.json"
    )
    _write_json_atomic(history, record)
    return {
        "ok": not errors,
        "checks": [{k: v for k, v in record.items() if k != "inputs"}],
        "errors": errors,
        "warnings": warnings,
        "checks_ref": ctx.ref(path),
    }
