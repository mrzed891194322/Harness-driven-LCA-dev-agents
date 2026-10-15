"""Map attempt-relative spec paths to on-disk locations (shared: spec_mcp + core)."""

from __future__ import annotations

_LEGACY_ATTEMPT_PATHS: dict[tuple[str, str], str] = {
    ("02-inventory-extraction", "extracted-bom.json"): (
        "workspace/outputs/inventory/extracted-bom.json"
    ),
    ("02-inventory-extraction", "extracted-bom.md"): (
        "workspace/outputs/inventory/extracted-bom.md"
    ),
    ("03-dataset-mapping", "LCI"): "workspace/outputs/LCI",
    ("03-dataset-mapping", "process-mapping.json"): (
        "workspace/outputs/inventory/process-mapping.json"
    ),
    ("03-dataset-mapping", "human_readable_mapping.md"): (
        "workspace/outputs/LCI/human_readable_mapping.md"
    ),
    ("04-openlca-reporting", "lca_report.md"): "workspace/outputs/reports/lca_report.md",
    ("04-openlca-reporting", "calculation-plan.json"): (
        "workspace/outputs/reports/calculation-plan.json"
    ),
    ("04-openlca-reporting", "results.json"): "workspace/artifacts/results.json",
}

_LEGACY_INPUT_FROM: dict[tuple[str, str], str] = {
    ("02-inventory-extraction", "extracted-bom.json"): (
        "workspace/outputs/inventory/extracted-bom.json"
    ),
    ("03-dataset-mapping", "LCI"): "workspace/outputs/LCI",
    ("03-dataset-mapping", "process-mapping.json"): (
        "workspace/outputs/inventory/process-mapping.json"
    ),
}


def legacy_workspace_path(stage_id: str, attempt_relative: str) -> str | None:
    return _LEGACY_ATTEMPT_PATHS.get((stage_id, attempt_relative.replace("\\", "/")))


def legacy_input_path(from_ref: str) -> str | None:
    text = from_ref.strip().replace("\\", "/")
    if "/" not in text:
        return None
    stage, name = text.split("/", 1)
    return _LEGACY_INPUT_FROM.get((stage, name))


def attempt_workspace_path(
    stage_id: str, role: str, attempt: int, declared: str
) -> str:
    name = str(declared or "").replace("\\", "/").lstrip("/")
    return f"workspace/runs/{stage_id}/{role}-{attempt}/{name}"


def resolve_declared_path(
    *,
    stage_id: str,
    declared: str,
    from_ref: str | None = None,
    role: str | None = None,
    attempt: int | None = None,
) -> str:
    text = str(declared or "").replace("\\", "/")
    if text.startswith("harness/") or text.startswith("workspace/"):
        return text
    if from_ref:
        mapped = legacy_input_path(from_ref)
        if mapped:
            return mapped
    if role and attempt:
        return attempt_workspace_path(stage_id, role, attempt, text)
    mapped = legacy_workspace_path(stage_id, text)
    if mapped:
        return mapped
    return text
