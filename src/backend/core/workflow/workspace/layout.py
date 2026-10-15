"""Workspace runs/ layout: attempt dirs, accepted.json, path resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from backend.core.workflow.workspace.legacy_paths import (
    legacy_input_path,
    legacy_workspace_path,
)


def inside(root: Path, relative: str) -> Path:
    text = str(relative).replace("\\", "/")
    if not text or Path(text).is_absolute() or ".." in Path(text).parts:
        raise ValueError(f"unsafe workspace path: {relative}")
    path = (root / text).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes workspace: {relative}")
    return path


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def stage_spec(project: Path, stage: str) -> dict[str, Any]:
    for base in (project / "harness/.user/specs", project / "harness/specs"):
        path = base / stage / "spec.yaml"
        if path.is_file():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
    return {}


def attempt_dir(workspace: Path, stage: str, role: str, attempt: int) -> Path:
    if role not in frozenset({"reviser", "executor", "system", "reviewer"}) or attempt < 1:
        raise ValueError("invalid attempt identity")
    return inside(workspace, f"runs/{stage}/{role}-{attempt}")


def attempts(workspace: Path, stage: str) -> list[dict[str, Any]]:
    raw = read_json(inside(workspace, f"runs/{stage}/attempts.json"), {})
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        items = raw.get("attempts")
        if isinstance(items, list):
            return items
    return []


def _attempt_row_dir(workspace: Path, stage: str, row: dict[str, Any]) -> Path:
    rel = str(row.get("dir") or row.get("path") or "").strip()
    if rel:
        text = rel.replace("\\", "/")
        if text.startswith("workspace/"):
            text = text[len("workspace/") :]
        return inside(workspace, text)
    return attempt_dir(
        workspace,
        stage,
        str(row["role"]),
        int(row["attempt"]),
    )


def writer_dir(workspace: Path, stage: str, attempt: int | None = None) -> Path:
    rows = [
        r
        for r in attempts(workspace, stage)
        if r.get("role") in frozenset({"reviser", "executor"})
        and (attempt is None or int(r.get("attempt") or 0) <= attempt)
    ]
    if rows:
        row = max(rows, key=lambda r: int(r.get("attempt") or 0))
        return _attempt_row_dir(workspace, stage, row)
    return attempt_dir(workspace, stage, "executor", attempt or 1)


def accepted(workspace: Path, stage: str) -> dict[str, Any]:
    raw = read_json(inside(workspace, f"runs/{stage}/accepted.json"), {})
    return raw if isinstance(raw, dict) else {}


def _legacy_workspace_file(workspace: Path, project_rel: str) -> Path:
    text = project_rel.replace("\\", "/")
    if text.startswith("workspace/"):
        text = text[len("workspace/") :]
    return inside(workspace, text)


def resolve_path(
    workspace: Path,
    project: Path,
    stage: str,
    declared: str,
    from_ref: str | None = None,
    role: str | None = None,
    attempt: int | None = None,
) -> Path:
    if from_ref:
        upstream, name = from_ref.split("/", 1)
        entry = accepted(workspace, upstream)
        rel = (entry.get("deliverables") or {}).get(name)
        if rel:
            return inside(workspace, str(rel))
        legacy = legacy_input_path(from_ref)
        if legacy:
            return _legacy_workspace_file(workspace, legacy)
        raise ValueError(f"upstream deliverable not accepted: {from_ref}")

    if declared.startswith("harness/"):
        return inside(project, declared)

    if declared.startswith("workspace/"):
        return inside(workspace, declared[len("workspace/") :])

    if role and role != "reviewer":
        base = attempt_dir(workspace, stage, role, attempt or 1)
    else:
        base = writer_dir(workspace, stage, attempt)

    candidate = inside(base, declared)
    if candidate.exists():
        return candidate

    if role and role != "reviewer":
        return candidate

    legacy = legacy_workspace_path(stage, declared)
    if legacy:
        return _legacy_workspace_file(workspace, legacy)

    return candidate


def handoff_file(
    workspace: Path, project: Path, stage: str, role: str, attempt: int
) -> Path:
    spec = stage_spec(project, stage)
    handoff = spec.get("handoff") or {}
    name = str(handoff.get("path") or "handoff.json")
    return inside(attempt_dir(workspace, stage, role, attempt), name)


def deliverable_deny_glob(
    project_root: Path,
    workspace: Path,
    stage_id: str,
    role: str,
    attempt: int,
    declared_path: str,
) -> str:
    return str(resolve_path(workspace, project_root, stage_id, declared_path,
                            role=role, attempt=attempt))



def declared_files(
    workspace: Path,
    project: Path,
    stage: str,
    role: str | None = None,
    attempt: int | None = None,
) -> list[Path]:
    spec = stage_spec(project, stage)
    paths: list[Path] = []
    for item in list(spec.get("inputs") or []) + list(spec.get("deliverables") or []):
        path = resolve_path(
            workspace,
            project,
            stage,
            str(item["path"]),
            item.get("from"),
            role,
            attempt,
        )
        if path.is_dir():
            paths.extend(
                p
                for p in sorted(path.rglob("*"))
                if p.is_file() and not p.is_symlink()
            )
        else:
            paths.append(path)
    return list(dict.fromkeys(paths))
