"""Workflow-page model choices.

The page default and per-assignment overrides live in
``.local/workflow-models.json``. An empty default means the page has not
chosen one. ``.env`` is not read or written for this choice.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.core.agents.catalog import split_pi_model_ref
from backend.core.runtime.capabilities import base_capabilities
from backend.core.runtime.model_profiles import load_profiles
from backend.core.workflow.config.loader import load_workflow
from backend.core.workflow.local_workflows import effective_workflow_path
from backend.core.workflow.config.models import Workflow

ASSIGNMENT_MODELS_PATH = Path(".local/workflow-models.json")
_ASSIGNMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
_WORKFLOW_ALIASES = {
    "whole-lca": "LCA-main.yaml",
    "LCA-main": "LCA-main.yaml",
    "LCA-main.yaml": "LCA-main.yaml",
    "revise-lca": "LCA-revise.yaml",
    "LCA-revise": "LCA-revise.yaml",
    "LCA-revise.yaml": "LCA-revise.yaml",
}


def _path(project_root: Path) -> Path:
    return project_root / ASSIGNMENT_MODELS_PATH


def _read_store(project_root: Path) -> dict:
    path = _path(project_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_store(project_root: Path, raw: dict) -> None:
    path = _path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_default_model(project_root: Path) -> str:
    """Page-saved default model. Missing or blank means none was chosen."""
    return str(_read_store(project_root).get("default") or "").strip()


def save_default_model(project_root: Path, model_ref: str) -> str:
    chosen = str(model_ref or "").strip()
    raw = _read_store(project_root)
    raw["default"] = chosen
    _write_store(project_root, raw)
    return chosen


def load_assignment_models(project_root: Path) -> dict[str, str]:
    raw = _read_store(project_root)
    assignments = raw.get("assignments")
    if not isinstance(assignments, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in assignments.items():
        assignment_id = str(key).strip()
        profile_id = str(value or "").strip()
        if _ASSIGNMENT_ID_RE.match(assignment_id) and profile_id:
            out[assignment_id] = profile_id
    return out


def save_assignment_models(project_root: Path, assignments: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in assignments.items():
        assignment_id = str(key).strip()
        profile_id = str(value or "").strip()
        if not _ASSIGNMENT_ID_RE.match(assignment_id):
            raise ValueError(f"未知分工：{assignment_id}")
        if profile_id:
            cleaned[assignment_id] = profile_id
    if len(cleaned) > 200:
        raise ValueError("分工模型过多")
    raw = _read_store(project_root)
    raw["assignments"] = cleaned
    _write_store(project_root, raw)
    return cleaned


def resolve_model_for_assignment(
    project_root: Path,
    workflow: Workflow,
    assignment_id: str,
    run_fallback: str,
) -> tuple[str, str, str | None, str | None]:
    """Return (effective, source, yaml_model, override_model).

    Precedence: assignment YAML model > workflow models.default > .local override > run_fallback.
    """
    assignment = workflow.assignments.get(assignment_id)
    yaml_model = (assignment.model or "").strip() if assignment else ""
    yaml_default = (workflow.models_default or "").strip()
    override = load_assignment_models(project_root).get(assignment_id, "").strip()
    local_default = load_default_model(project_root)

    if yaml_model:
        _validate_model_ref(project_root, yaml_model)
        return yaml_model, "yaml", yaml_model, override or None
    if yaml_default:
        _validate_model_ref(project_root, yaml_default)
        return yaml_default, "yaml_default", None, override or None
    if override:
        _validate_model_ref(project_root, override)
        return override, "override", None, override
    if local_default:
        _validate_model_ref(project_root, local_default)
        return local_default, "override_default", None, None
    return run_fallback, "run", None, None


def list_models_for_workflow(
    project_root: Path,
    *,
    workflow_name: str,
    run_fallback: str,
) -> dict[str, dict[str, str | None]]:
    workflow = _load_workflow_for_name(project_root, workflow_name)
    if workflow is None:
        return {}
    rows: dict[str, dict[str, str | None]] = {}
    for assignment_id in sorted(workflow.assignments):
        effective, source, yaml_model, override_model = resolve_model_for_assignment(
            project_root, workflow, assignment_id, run_fallback
        )
        rows[assignment_id] = {
            "model": effective,
            "source": source,
            "yaml_model": yaml_model,
            "override_model": override_model,
        }
    return rows


def _validate_model_ref(project_root: Path, model_ref: str) -> None:
    if model_ref in load_profiles(project_root):
        return
    provider, model_id = split_pi_model_ref(model_ref)
    if provider and model_id:
        return
    raise ValueError(f"unknown model name in workflow YAML: {model_ref!r}")


def _load_workflow_for_name(project_root: Path, workflow_name: str) -> Workflow | None:
    key = workflow_name.strip()
    filename = _WORKFLOW_ALIASES.get(key)
    if not filename:
        raise ValueError(f"unknown workflow name: {workflow_name}")
    path = effective_workflow_path(project_root, filename)
    if not path.is_file():
        return None
    return load_workflow(
        path,
        project_root=project_root,
        capabilities=base_capabilities(),
    )


def model_for_assignment(
    project_root: Path,
    assignment_id: str,
    fallback: str,
    workflow: Workflow | None = None,
) -> str:
    """Return one assignment's model ref, or the run-wide model."""
    if workflow is not None:
        effective, _, _, _ = resolve_model_for_assignment(
            project_root, workflow, assignment_id, fallback
        )
        return effective
    chosen = load_assignment_models(project_root).get(assignment_id, "").strip()
    if not chosen:
        return fallback
    if chosen in load_profiles(project_root):
        return chosen
    provider, model_id = split_pi_model_ref(chosen)
    if provider and model_id:
        return chosen
    return fallback
