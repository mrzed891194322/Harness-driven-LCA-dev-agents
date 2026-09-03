"""Load whole-lca / revise-lca workflow YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ALLOWED_ROLES = frozenset({"executor", "reviewer"})


@dataclass(frozen=True)
class Assignment:
    key: str
    role: str
    spec: str
    prompt: str


@dataclass(frozen=True)
class Step:
    role: str
    assignment: str


@dataclass(frozen=True)
class Stage:
    id: str
    spec: str
    max_attempts: int
    steps: tuple[Step, ...]
    cover_plan_from: str | None = None


@dataclass(frozen=True)
class Workflow:
    id: str
    path: Path
    max_attempts: int
    stages: tuple[Stage, ...]
    preamble: tuple[Stage, ...]
    assignments: dict[str, Assignment]
    overlays: dict[str, str]


def load_workflow(path: Path) -> Workflow:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"workflow is not a mapping: {path}")
    if "mcp" in raw:
        raise ValueError(f"workflow must not set mcp for the orchestrator: {path}")

    assignments = _load_assignments(raw.get("assignments") or {})
    overlays = {
        key: str((value or {}).get("extra_prompt") or "")
        for key, value in (raw.get("overlays") or {}).items()
    }
    reused: Workflow | None = None
    reuse = raw.get("reuse")
    if reuse:
        reused = load_workflow(_resolve(path, str(reuse)))
        merged = dict(reused.assignments)
        merged.update(assignments)
        assignments = merged
        overlay_merged = dict(reused.overlays)
        overlay_merged.update(overlays)
        overlays = overlay_merged

    stages = tuple(_load_stage(item, default_attempts=int(raw.get("max_attempts") or 3)) for item in (raw.get("stages") or ()))
    if reused is not None and not stages:
        stages = reused.stages
    preamble = tuple(
        _load_stage(item, default_attempts=1) for item in (raw.get("preamble") or ())
    )
    workflow_id = str(raw.get("id") or path.stem)
    return Workflow(
        id=workflow_id,
        path=path,
        max_attempts=int(raw.get("max_attempts") or 3),
        stages=stages,
        preamble=preamble,
        assignments=assignments,
        overlays=overlays,
    )


def _resolve(from_path: Path, relative: str) -> Path:
    root = next(parent for parent in from_path.parents if (parent / "pyproject.toml").is_file())
    return root / relative


def _load_assignments(raw: dict[str, Any]) -> dict[str, Assignment]:
    loaded: dict[str, Assignment] = {}
    for key, item in raw.items():
        role = str(item.get("role") or "")
        if role not in ALLOWED_ROLES:
            raise ValueError(f"unknown assignment role {role!r} for {key}")
        if "mcp" in item:
            raise ValueError(f"assignment {key} must not set mcp")
        prompt = str(item.get("prompt") or "").strip()
        spec = str(item.get("spec") or "").strip()
        if not prompt or not spec:
            raise ValueError(f"assignment {key} needs spec and prompt")
        loaded[key] = Assignment(key=key, role=role, spec=spec, prompt=prompt)
    return loaded


def _load_stage(raw: dict[str, Any], *, default_attempts: int) -> Stage:
    stage_id = str(raw["id"])
    steps = tuple(
        Step(role=str(step["role"]), assignment=str(step["assignment"]))
        for step in raw.get("steps") or ()
    )
    if not steps:
        raise ValueError(f"stage {stage_id} has no steps")
    for step in steps:
        if step.role not in ALLOWED_ROLES:
            raise ValueError(f"stage {stage_id} has unknown role {step.role}")
    return Stage(
        id=stage_id,
        spec=str(raw["spec"]),
        max_attempts=int(raw.get("max_attempts") or default_attempts),
        steps=steps,
        cover_plan_from=str(raw["cover_plan_from"]) if raw.get("cover_plan_from") else None,
    )
