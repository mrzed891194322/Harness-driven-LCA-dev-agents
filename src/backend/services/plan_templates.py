"""YAML-driven LCA plan form templates (GUI materializes sections from these files)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

TEMPLATES_DIR = Path("harness/plan-templates")


class PlanTemplateError(ValueError):
    """Unknown or invalid plan template."""


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PlanTemplateError(f"模板不是对象：{path}")
    return data


def list_plan_templates(root: Path) -> list[dict[str, Any]]:
    folder = root / TEMPLATES_DIR
    if not folder.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.yaml")):
        try:
            data = _load_yaml(path)
        except (OSError, yaml.YAMLError, PlanTemplateError):
            continue
        tid = str(data.get("id") or path.stem)
        sections = data.get("sections") or []
        out.append(
            {
                "id": tid,
                "title": data.get("title") or tid,
                "title_en": data.get("title_en") or data.get("title") or tid,
                "description": data.get("description") or "",
                "description_en": data.get("description_en") or data.get("description") or "",
                "align_workflows": list(data.get("align_workflows") or []),
                "section_ids": [
                    str(s.get("id")) for s in sections if isinstance(s, dict) and s.get("id")
                ],
                "path": f"{TEMPLATES_DIR.as_posix()}/{path.name}",
            }
        )
    return out


def get_plan_template(root: Path, template_id: str) -> dict[str, Any]:
    key = (template_id or "").strip()
    if not key:
        raise PlanTemplateError("缺少模板 id")
    folder = root / TEMPLATES_DIR
    path = folder / f"{key}.yaml"
    if not path.is_file():
        # allow id mismatch vs filename
        for candidate in sorted(folder.glob("*.yaml")) if folder.is_dir() else []:
            data = _load_yaml(candidate)
            if str(data.get("id") or candidate.stem) == key:
                path = candidate
                break
        else:
            raise PlanTemplateError(f"未知计划模板：{key}")
    data = _load_yaml(path)
    sections = []
    for raw in data.get("sections") or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        sections.append(
            {
                "id": str(raw["id"]),
                "required": bool(raw.get("required", True)),
            }
        )
    return {
        "id": str(data.get("id") or path.stem),
        "title": data.get("title") or path.stem,
        "title_en": data.get("title_en") or data.get("title") or path.stem,
        "description": data.get("description") or "",
        "description_en": data.get("description_en") or data.get("description") or "",
        "align_workflows": list(data.get("align_workflows") or []),
        "sections": sections,
        "path": f"{TEMPLATES_DIR.as_posix()}/{path.name}",
    }
