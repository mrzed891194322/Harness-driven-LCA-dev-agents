"""Thin-spec frontmatter parser for orchestrator acceptance checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_FRONTMATTER = re.compile(r"\A---\s*\n(?P<header>.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class StageSpec:
    spec_id: str
    path: Path
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]


def load_stage_spec(path: Path) -> StageSpec:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        raise ValueError(f"spec missing YAML front matter: {path}")
    header = yaml.safe_load(match.group("header")) or {}
    spec_id = str(header.get("id") or path.parent.name)
    inputs = tuple(str(item) for item in (header.get("inputs") or ()))
    outputs = tuple(str(item) for item in (header.get("outputs") or ()))
    if not outputs:
        raise ValueError(f"spec has no outputs: {path}")
    return StageSpec(spec_id=spec_id, path=path, inputs=inputs, outputs=outputs)


def missing_outputs(project_root: Path, outputs: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for relative in outputs:
        target = project_root / relative
        if not target.exists():
            missing.append(relative)
            continue
        if target.is_file() and target.stat().st_size == 0:
            missing.append(relative)
    return missing
