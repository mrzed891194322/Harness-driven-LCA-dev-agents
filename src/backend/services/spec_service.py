"""Spec parts for the GUI: read default vs user override, save override, validate.

Every stage spec part lives at ``harness/specs/<stage>/<part>``; a GUI save only
writes ``harness/.user/specs/<stage>/<part>`` (gitignored) and never touches the
default. ``validate`` runs the core loader, which checks the manifest, that every
schema is a valid JSON Schema and that every example passes its schema. Saving
an override that would make the spec invalid is rejected (the previous user
version is restored), so the next session never picks up a broken spec.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from backend.core.runtime import harness_fs
from backend.core.runtime.identifiers import require_identifier
from backend.core.workflow.spec.loader import load_stage_spec
from backend.core.workflow.spec.view import spec_view, spec_view_hash

PART_SUFFIXES = (".yaml", ".yml", ".json")


class SpecPartError(ValueError):
    pass


def _stage(stage: str) -> str:
    try:
        return require_identifier(stage, label="stage")
    except ValueError as exc:
        raise SpecPartError(str(exc)) from exc


def _part(part: str) -> str:
    text = str(part or "").replace("\\", "/").strip()
    pieces = [p for p in text.split("/") if p]
    if not pieces or text.startswith("/") or any(p in (".", "..") or p.startswith(".") for p in pieces):
        raise SpecPartError(f"invalid spec part {part!r}")
    if not text.endswith(PART_SUFFIXES):
        raise SpecPartError("spec parts are .yaml or .json files (no Markdown in specs)")
    return "/".join(pieces)


def _rel(stage: str, part: str) -> str:
    return f"specs/{_stage(stage)}/{_part(part)}"


def list_specs(project_root: Path) -> dict[str, Any]:
    stages = []
    roots = [project_root / "harness" / "specs", project_root / "harness" / ".user" / "specs"]
    names = sorted({p.name for r in roots if r.is_dir() for p in r.iterdir() if p.is_dir()})
    for name in names:
        parts: dict[str, str] = {}
        for base, source in ((roots[0] / name, "default"), (roots[1] / name, "user")):
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*")):
                if path.is_file() and path.suffix in PART_SUFFIXES:
                    rel = path.relative_to(base).as_posix()
                    parts[rel] = "user" if source == "user" or parts.get(rel) == "user" else source
        stages.append(
            {"id": name, "parts": [{"path": k, "source": v} for k, v in sorted(parts.items())]}
        )
    return {"stages": stages}


def read_part(project_root: Path, stage: str, part: str) -> dict[str, Any]:
    rel = _rel(stage, part)
    default = harness_fs.default_path(project_root, rel)
    user = harness_fs.user_path(project_root, rel)
    if not default.is_file() and not user.is_file():
        raise FileNotFoundError(rel)
    return {
        "stage": stage,
        "path": part,
        "default": default.read_text(encoding="utf-8") if default.is_file() else None,
        "override": user.read_text(encoding="utf-8") if user.is_file() else None,
        "effective": "user" if user.is_file() else "default",
    }


def _parse(part: str, content: str) -> None:
    try:
        if part.endswith(".json"):
            json.loads(content)
        else:
            yaml.safe_load(content)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise SpecPartError(f"{part}: {exc}") from exc


def validate_spec(project_root: Path, stage: str) -> dict[str, Any]:
    stage = _stage(stage)
    relative = f"harness/specs/{stage}/spec.yaml"
    try:
        spec = load_stage_spec(project_root / relative, project_root=project_root, relative=relative)
    except (OSError, ValueError) as exc:
        return {"stage": stage, "ok": False, "errors": [str(exc)]}
    view = spec_view(spec, project_root)
    return {
        "stage": stage,
        "ok": True,
        "errors": [],
        "spec_hash": spec_view_hash(view),
        "sources": {k: v["source"] for k, v in spec.sources.items()},
        "deliverables": [d.name for d in spec.deliverables],
    }


def save_override(project_root: Path, stage: str, part: str, content: str) -> dict[str, Any]:
    rel = _rel(stage, part)
    _parse(part, content)
    user = harness_fs.user_path(project_root, rel)
    previous = user.read_bytes() if user.is_file() else None
    user.parent.mkdir(parents=True, exist_ok=True)
    user.write_text(content, encoding="utf-8")
    result = validate_spec(project_root, stage) if stage != "shared" else {"ok": True, "errors": []}
    if not result["ok"]:
        if previous is None:
            user.unlink()
        else:
            user.write_bytes(previous)
        raise SpecPartError("; ".join(result["errors"]))
    return {"saved": True, "path": part, "validation": result}


def reset_override(project_root: Path, stage: str, part: str) -> dict[str, Any]:
    user = harness_fs.user_path(project_root, _rel(stage, part))
    existed = user.is_file()
    if existed:
        user.unlink()
    return {"reset": existed, "path": part}


def specs_health(project_root: Path) -> dict[str, Any]:
    """Doctor-style check of every stage spec (paths after the P5 move)."""
    results = [
        validate_spec(project_root, s["id"])
        for s in list_specs(project_root)["stages"]
        if s["id"] != "shared"
    ]
    shared = project_root / "harness" / "specs" / "shared" / "permissions"
    errors = [e for r in results for e in r["errors"]]
    if not shared.is_dir():
        errors.append("missing harness/specs/shared/permissions/")
    legacy = [
        p for p in ("harness/rules/permissions", "harness/rules/prompts")
        if (project_root / p).exists()
    ]
    errors.extend(f"legacy path still present: {p} (moved in P5)" for p in legacy)
    return {"ok": not errors, "errors": errors, "stages": results}
