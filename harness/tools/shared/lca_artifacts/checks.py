"""Offline checks and dependency invalidation, independent of stage advancement."""

from __future__ import annotations

import json
import re
from pathlib import Path

from harness.tools.shared.control_openlca.guard import file_lock
from harness.tools.shared.control_openlca.workflow import (
    _write_json_atomic,
    stable_hash,
    utc_now,
)
from harness.tools.shared.lca_artifacts import offline_checks as artifact_checks
from harness.tools.shared.lca_artifacts.path_safety import require_relative_path

from .snapshot_io import check_snapshot, load_json, sha256_file

CHECKER_VERSION = "3.0"
# Internal profile ids for Host Action checks and MCP-adjacent validation.
# Must NOT map to workflow stage ids.
INTERNAL_PROFILES = frozenset({"inventory", "mapping", "report"})
ACCEPTANCE_MODEL = "lca.model"
# Backward-compatible alias for MCP Literal / callers that still import PROFILES.
PROFILES = {name: name for name in sorted(INTERNAL_PROFILES)}
SNAPSHOT_SCOPES = frozenset({"workspace", "project"})


def load(path):
    return load_json(Path(path))


def _load_source_manifest(ctx) -> dict | None:
    path = ctx.sources_manifest_path()
    if not path.is_file():
        return None
    try:
        payload = load(path)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def declared_source_ids(ctx) -> set[str]:
    """Source ids declared by the host-owned source manifest (files + sources)."""
    payload = _load_source_manifest(ctx)
    if payload is None:
        return set()
    declared: set[str] = set()
    for entry in payload.get("files") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("readable") is not True:
            continue
        relative = entry.get("path")
        if not relative:
            continue
        try:
            path = require_relative_path(str(relative), label="source manifest path")
        except ValueError:
            continue
        declared.add(path.replace("\\", "/"))
    for entry in payload.get("sources") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("available") is not True:
            continue
        source_id = entry.get("id")
        if not source_id:
            continue
        declared.add(str(source_id))
    return declared


def declared_local_sources(ctx) -> set[str]:
    """Backward-compatible alias for readable local file paths in the manifest."""
    payload = _load_source_manifest(ctx)
    if payload is None:
        return set()
    declared: set[str] = set()
    for entry in payload.get("files") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("readable") is not True:
            continue
        relative = entry.get("path")
        if not relative:
            continue
        try:
            path = require_relative_path(str(relative), label="source manifest path")
        except ValueError:
            continue
        declared.add(path.replace("\\", "/"))
    return declared


def knowledge_files_from_manifest(ctx) -> list[Path]:
    """Readable files listed in the assignment-scoped source manifest."""
    payload = _load_source_manifest(ctx)
    if payload is None:
        return []
    files = []
    project = ctx.project.resolve()
    for entry in payload.get("files") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("readable") is not True:
            continue
        relative = entry.get("path")
        if not relative:
            continue
        try:
            rel = require_relative_path(str(relative), label="source manifest path")
            candidate = (ctx.project / rel).resolve()
        except (OSError, ValueError):
            continue
        if candidate != project and project not in candidate.parents:
            continue
        if not candidate.is_file():
            continue
        files.append(candidate)
    return files


def _safe_lci_files(lci_root: Path) -> list[Path]:
    """Enumerate LCI files without following escape/symlink targets."""
    if not lci_root.exists():
        return []
    try:
        root = lci_root.resolve()
    except OSError:
        return []
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved != root and root not in resolved.parents:
            continue
        files.append(path)
    return files


def upstream_files(ctx):
    plan_dir = ctx.project / "harness" / "knowledge" / "plan"
    paths = [
        plan_dir / "main_plan.md",
        ctx.workspace / "outputs" / "inventory" / "extracted-bom.json",
        ctx.workspace / "outputs" / "inventory" / "process-mapping.json",
    ]
    revise_plan = plan_dir / "revise_plan.md"
    if revise_plan.exists():
        paths.append(revise_plan)
    lci_root = ctx.workspace / "outputs" / "LCI"
    paths.extend(_safe_lci_files(lci_root))
    paths.extend(knowledge_files_from_manifest(ctx))
    return paths


def fingerprints(paths):
    return {
        str(p.resolve()): sha256_file(p) if p.is_file() else "missing" for p in paths
    }


def scoped_fingerprints(ctx, paths) -> list[dict[str, str]]:
    """Stable scoped file entries for check/acceptance snapshots."""
    entries: list[dict[str, str]] = []
    workspace = ctx.workspace.resolve()
    project = ctx.project.resolve()
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        scope = None
        rel = None
        try:
            rel = str(resolved.relative_to(workspace)).replace("\\", "/")
            scope = "workspace"
        except ValueError:
            try:
                rel = str(resolved.relative_to(project)).replace("\\", "/")
                scope = "project"
            except ValueError:
                continue
        try:
            require_relative_path(rel, label="snapshot path")
        except ValueError:
            continue
        entries.append(
            {
                "scope": scope,
                "path": rel,
                "sha256": sha256_file(resolved) if resolved.is_file() else "missing",
            }
        )
    return sorted(entries, key=lambda item: (item["scope"], item["path"]))


def relative_fingerprints(ctx, paths) -> list[dict[str, str]]:
    """Alias kept for callers; returns scoped fingerprint entries."""
    return scoped_fingerprints(ctx, paths)


def model_fingerprint(ctx):
    return stable_hash(scoped_fingerprints(ctx, upstream_files(ctx)))


def model_inputs_snapshot(ctx) -> dict:
    return {
        "files": scoped_fingerprints(ctx, upstream_files(ctx)),
    }


def accepted_model_fingerprint(ctx) -> str | None:
    accepted = ctx.load_manifest().get("accepted", {}).get(ACCEPTANCE_MODEL)
    if not isinstance(accepted, dict):
        return None
    value = accepted.get("model_fingerprint")
    return str(value) if value else None


def evidence_model_fingerprint(ctx) -> str:
    """Fingerprint stamped on / compared against raw evidence calls.

    Report phase uses the accepted mapping model fingerprint so report-only
    knowledge changes do not invalidate import/calc evidence.
    """
    phase = None
    if hasattr(ctx, "lca_phase"):
        getter = ctx.lca_phase
        phase = getter() if callable(getter) else getter
    if phase is None:
        phase = getattr(ctx, "stage", None)
    if phase == "report":
        accepted = accepted_model_fingerprint(ctx)
        if accepted:
            return accepted
    return model_fingerprint(ctx)


def resolve_snapshot_path(ctx, entry: dict | str) -> Path:
    """Resolve a scoped snapshot entry (or legacy string key) to an absolute path."""
    if isinstance(entry, str):
        # Legacy flat keys are no longer authoritative; treat as project-relative
        # only when they do not look like workspace layout, else workspace.
        key = require_relative_path(entry, label="legacy snapshot path")
        root = ctx.project
        resolved = (root / key).resolve()
        _assert_scope_containment(root, resolved, scope="project")
        return resolved
    if not isinstance(entry, dict):
        raise ValueError("snapshot entry must be a mapping")
    scope = str(entry.get("scope") or "")
    if scope not in SNAPSHOT_SCOPES:
        raise ValueError(f"unknown snapshot scope: {scope!r}")
    rel = require_relative_path(str(entry.get("path") or ""), label="snapshot path")
    root = ctx.workspace if scope == "workspace" else ctx.project
    resolved = (root / rel).resolve()
    _assert_scope_containment(root, resolved, scope=scope)
    return resolved


def _assert_scope_containment(root: Path, resolved: Path, *, scope: str) -> None:
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"snapshot path escapes {scope} root")


def _normalize_file_entries(files: object) -> list[dict[str, str]]:
    if isinstance(files, list):
        entries: list[dict[str, str]] = []
        for item in files:
            if not isinstance(item, dict):
                continue
            scope = str(item.get("scope") or "")
            path = str(item.get("path") or "")
            digest = str(item.get("sha256") or "missing")
            if scope not in SNAPSHOT_SCOPES:
                continue
            try:
                path = require_relative_path(path, label="snapshot path")
            except ValueError:
                continue
            entries.append({"scope": scope, "path": path, "sha256": digest})
        return sorted(entries, key=lambda item: (item["scope"], item["path"]))
    if isinstance(files, dict):
        # Legacy flat map → treat keys as project-relative for migration only.
        entries = []
        for key, digest in files.items():
            try:
                path = require_relative_path(str(key), label="legacy snapshot path")
            except ValueError:
                continue
            entries.append({"scope": "project", "path": path, "sha256": str(digest)})
        return sorted(entries, key=lambda item: (item["scope"], item["path"]))
    return []


def snapshot_current_hashes(ctx, snapshot: dict) -> list[dict[str, str]]:
    files = snapshot.get("files") or []
    current: list[dict[str, str]] = []
    for entry in _normalize_file_entries(files):
        try:
            path = resolve_snapshot_path(ctx, entry)
            digest = sha256_file(path) if path.is_file() else "missing"
        except (OSError, ValueError):
            digest = "missing"
        current.append(
            {
                "scope": entry["scope"],
                "path": entry["path"],
                "sha256": digest,
            }
        )
    return sorted(current, key=lambda item: (item["scope"], item["path"]))


def snapshot_unchanged(ctx, snapshot: dict) -> bool:
    expected = _normalize_file_entries(snapshot.get("files") or [])
    current = snapshot_current_hashes(ctx, {"files": expected})
    if expected != current:
        return False
    if "evidence_refs" in snapshot:
        return not _evidence_refs_changed(ctx, snapshot.get("evidence_refs"))
    return True


def calculation_path(ctx):
    return ctx.safe(ctx.workspace / "outputs" / "reports" / "calculation-plan.json")


def calculation_fingerprint(ctx):
    path = calculation_path(ctx)
    return sha256_file(path) if path.is_file() else "missing"


def record_acceptance(ctx, *, acceptance_key: str = ACCEPTANCE_MODEL):
    """Persist acceptance from the frozen mapping check inputs (not live snapshot)."""
    record = validation_state(ctx, "mapping")
    if record.get("status") != "passed":
        raise ValueError(
            "mapping check must be passed before recording acceptance; "
            f"status={record.get('status')!r}"
        )
    producer_stage = record.get("stage")
    if producer_stage != ctx.stage:
        raise ValueError(
            "mapping check producer stage must match current stage; "
            f"check_stage={producer_stage!r} current={ctx.stage!r}"
        )
    inputs = record.get("inputs")
    if not isinstance(inputs, dict) or "files" not in inputs:
        raise ValueError("mapping check record missing frozen inputs")
    files = _normalize_file_entries(inputs.get("files"))
    frozen = {"files": files}
    if "evidence_refs" in inputs:
        refs = inputs["evidence_refs"]
        if _evidence_refs_changed(ctx, refs):
            raise ValueError("mapping check evidence refs are stale")
        frozen["evidence_refs"] = refs
    with file_lock(ctx.safe(ctx.memory / "manifest.lock")):
        value = ctx.load_manifest()
        value["accepted"][acceptance_key] = {
            "model_fingerprint": stable_hash(files),
            "inputs": frozen,
            "at": utc_now(),
            "attempt": ctx.attempt,
            "stage": ctx.stage,
            "assignment": ctx.assignment,
        }
        _write_json_atomic(ctx.manifest, value)


def require_approved_model(ctx, *, allow_reviewer=False):
    if ctx.stage == "standalone":
        return
    phase = None
    if hasattr(ctx, "lca_phase"):
        getter = ctx.lca_phase
        phase = getter() if callable(getter) else getter
    if phase is None:
        phase = getattr(ctx, "stage", None)
    if phase != "report" or (ctx.role == "reviewer" and not allow_reviewer):
        raise ValueError("only report-phase writer can import or calculate")
    accepted = ctx.load_manifest()["accepted"].get(ACCEPTANCE_MODEL)
    if not accepted:
        raise ValueError("approved model missing or stale; upstream review required")
    snapshot = accepted.get("inputs")
    if isinstance(snapshot, dict) and snapshot.get("files") is not None:
        if not snapshot_unchanged(ctx, snapshot):
            raise ValueError(
                "approved model missing or stale; upstream review required"
            )
        return
    # Legacy records: compare opaque fingerprint against current assignment inputs.
    if accepted.get("model_fingerprint") != model_fingerprint(ctx):
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
    accepted = ctx.load_manifest().get("accepted", {}).get(ACCEPTANCE_MODEL)
    if isinstance(accepted, dict):
        snapshot = accepted.get("inputs")
        if isinstance(snapshot, dict) and snapshot.get("files") is not None:
            if not snapshot_unchanged(ctx, snapshot):
                raise ValueError("raw evidence is stale relative to approved inputs")
    expected = evidence_model_fingerprint(ctx)
    result = []
    for call in calls:
        raw = load(ctx.resolve_ref(call["artifact"]))
        if call.get("model_fingerprint") != expected:
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
        accepted = ctx.load_manifest()["accepted"].get(ACCEPTANCE_MODEL, {})
        snapshot = accepted.get("inputs")
        if isinstance(snapshot, dict) and snapshot.get("files") is not None:
            unchanged = snapshot_unchanged(ctx, snapshot)
        else:
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
    return artifact_checks.inventory_errors(rows, declared_source_ids(ctx))


def mapping_errors(ctx):
    bom = _items(ctx.workspace / "outputs" / "inventory" / "extracted-bom.json")
    mapping = _items(ctx.workspace / "outputs" / "inventory" / "process-mapping.json")
    # Preflight and exact-pair batch checks are accepted formal provider evidence.
    found = set()
    fingerprint = model_fingerprint(ctx)
    for call in ctx.load_manifest()["calls"]:
        if call["tool"] not in {"preflight_import_lci", "validate_providers_batch"}:
            continue
        if call.get("model_fingerprint") != fingerprint:
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
    return artifact_checks.mapping_errors(
        bom, mapping, ctx.workspace / "outputs" / "LCI", found
    )


def _source_manifest_ref(ctx) -> dict[str, str] | None:
    path = ctx.sources_manifest_path()
    if not path.is_file():
        return None
    return {
        "path": str(path.relative_to(ctx.workspace)).replace("\\", "/"),
        "sha256": sha256_file(path),
    }


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
    refs = current_evidence_refs(ctx, profile, ctx.stage)
    paths += [ctx.safe(ctx.workspace / ref["path"]) for ref in refs]
    payload: dict = {
        "files": scoped_fingerprints(ctx, paths),
        "evidence_refs": refs,
    }
    manifest_ref = _source_manifest_ref(ctx)
    if manifest_ref is not None:
        payload["source_manifest"] = manifest_ref
    return payload


PROFILE_EVIDENCE_TOOLS = {
    "inventory": frozenset(),
    "mapping": frozenset({"preflight_import_lci", "validate_providers_batch"}),
    "report": frozenset({"import_lci", "get_model_graph", "calculate_product_system"}),
}


def _normalize_evidence_refs(refs: object) -> list[dict[str, str]]:
    if not isinstance(refs, list):
        return []
    normalized: list[dict[str, str]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        path = str(ref.get("path") or "")
        digest = str(ref.get("sha256") or "")
        if not path or not digest:
            continue
        try:
            path = require_relative_path(path, label="evidence ref path")
        except ValueError:
            continue
        normalized.append({"path": path, "sha256": digest})
    return sorted(normalized, key=lambda item: (item["path"], item["sha256"]))


def current_evidence_refs(ctx, profile: str, producer_stage: str) -> list[dict]:
    """Stable evidence artifact refs for the profile's relevant MCP calls."""
    tools = PROFILE_EVIDENCE_TOOLS.get(profile)
    if tools is None:
        raise ValueError("unknown check profile")
    refs = []
    for call in ctx.load_manifest()["calls"]:
        tool = call.get("evidence_tool", call.get("tool"))
        if tool not in tools:
            continue
        if call.get("stage") != producer_stage:
            continue
        artifact = call.get("artifact")
        if not isinstance(artifact, dict):
            continue
        refs.append(artifact)
    return _normalize_evidence_refs(refs)


def check_path(ctx, profile):
    if profile not in INTERNAL_PROFILES:
        raise ValueError("unknown check profile")
    return ctx.safe(ctx.memory / "checks" / f"{profile}.json")


def validation_state_for_run(ctx, profile):
    return validation_state(ctx, profile)


def _evidence_refs_changed(ctx, stored_refs: object) -> bool:
    expected = _normalize_evidence_refs(stored_refs)
    for ref in expected:
        try:
            ctx.resolve_ref(ref)
        except (OSError, ValueError, KeyError, TypeError):
            return True
    return False


def _evidence_membership_changed(ctx, profile: str, record: dict) -> bool:
    tools = PROFILE_EVIDENCE_TOOLS.get(profile)
    if not tools:
        return False
    stored = (record.get("inputs") or {}).get("evidence_refs")
    producer_stage = record.get("stage") or ctx.stage
    expected = _normalize_evidence_refs(stored)
    current = current_evidence_refs(ctx, profile, producer_stage)
    return expected != current


def _source_manifest_changed(ctx, stored_ref: object) -> bool:
    if not isinstance(stored_ref, dict):
        return True
    path = str(stored_ref.get("path") or "")
    digest = str(stored_ref.get("sha256") or "")
    if not path or not digest:
        return True
    try:
        path = require_relative_path(path, label="source manifest path")
        current = ctx.safe(ctx.workspace / path)
    except (OSError, ValueError):
        return True
    if not current.is_file():
        return True
    return sha256_file(current) != digest


def _stored_inputs_changed(ctx, stored_inputs: dict) -> bool:
    """Re-hash frozen files and verify frozen evidence refs; do not rebuild files."""
    if not isinstance(stored_inputs, dict):
        return True
    files = stored_inputs.get("files")
    if files is None:
        return True
    expected = _normalize_file_entries(files)
    if isinstance(files, dict) and files and not expected:
        return True
    current = snapshot_current_hashes(ctx, {"files": expected})
    if expected != current:
        return True
    if "evidence_refs" in stored_inputs:
        if _evidence_refs_changed(ctx, stored_inputs.get("evidence_refs")):
            return True
    if "source_manifest" in stored_inputs:
        if _source_manifest_changed(ctx, stored_inputs.get("source_manifest")):
            return True
    return False


@check_snapshot
def validation_state(ctx, profile):
    path = check_path(ctx, profile)
    if not path.exists():
        return {
            "check_id": profile,
            "checker_version": CHECKER_VERSION,
            "status": "not_run",
        }
    record = load(path)
    stale = False
    if record.get("checker_version") != CHECKER_VERSION:
        stale = True
    elif _stored_inputs_changed(ctx, record.get("inputs") or {}):
        stale = True
    elif _evidence_membership_changed(ctx, profile, record):
        stale = True
    if stale:
        record = {**record, "status": "stale"}
        _write_json_atomic(path, record)
    return record


def validate(ctx, profile):
    """MCP-facing validate: still checks profile membership; orchestrator uses validate_for_run."""
    if profile not in INTERNAL_PROFILES:
        raise ValueError("unknown check profile")
    return validate_for_run(ctx, profile)


@check_snapshot
def validate_for_run(ctx, profile):
    if profile not in INTERNAL_PROFILES:
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
        "stage": ctx.stage,
        "assignment": ctx.assignment,
        "attempt": ctx.attempt,
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
