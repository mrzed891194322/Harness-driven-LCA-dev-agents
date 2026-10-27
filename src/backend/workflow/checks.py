"""Host-side checks: requires preflight and generic JSON-Schema validation of produces."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from backend.workflow.config import Node, Spec


def _parse_error(path: Path) -> str | None:
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"无法读取：{exc}"
    if not text.strip():
        return "文件为空"
    try:
        if suffix == ".json":
            json.loads(text)
        elif suffix in (".yaml", ".yml"):
            yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        return f"无法解析：{exc}"
    return None


def check_path(path: Path) -> str | None:
    """None when ``path`` is a usable artifact; otherwise a reason."""
    if not path.exists():
        return "不存在"
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        if not files:
            return "目录为空"
        for file in files:
            reason = _parse_error(file)
            if reason:
                return f"{file.name} {reason}"
        return None
    return _parse_error(path)


def _nonempty_error(path: Path) -> str | None:
    """Exists + non-empty only (no structural parse). Used for freeform plan text."""
    if not path.exists():
        return "不存在"
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        if not files:
            return "目录为空"
        for file in files:
            try:
                text = file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                return f"{file.name} 无法读取：{exc}"
            if not text.strip():
                return f"{file.name} 文件为空"
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"无法读取：{exc}"
    if not text.strip():
        return "文件为空"
    return None


def requires_errors(artifacts: Path, node: Node, plan_required: bool = True) -> list[str]:
    """Plan under artifacts/plan may be NL query or form YAML; inject reads it as text.
    Do not yaml.safe_load plan files here — ASCII ': ' in freeform NL (e.g. PCFBench
    query.md) is valid plan text but invalid YAML and would false-fail requires.
    """
    errors = []
    if plan_required:
        reason = _nonempty_error(artifacts / "plan")
        if reason:
            errors.append(f"requires plan: {reason}")
    for rel in node.requires:
        reason = check_path(artifacts / rel)
        if reason:
            errors.append(f"requires {rel}: {reason}")
    return errors


def produce_errors(artifacts: Path, node: Node, specs: dict[str, Spec]) -> list[str]:
    import jsonschema

    errors = []
    for prod in node.produces:
        target = artifacts / prod.path
        reason = check_path(target)
        if reason:
            errors.append(f"交付物 {prod.path}: {reason}")
            continue
        spec = specs[prod.spec]
        if spec.schema_ is None:
            continue
        files = [target] if target.is_file() else sorted(target.rglob("*.json"))
        for file in files:
            if file.suffix.lower() != ".json":
                continue
            data = json.loads(file.read_text(encoding="utf-8"))
            for err in jsonschema.Draft202012Validator(spec.schema_).iter_errors(data):
                where = "/".join(str(p) for p in err.absolute_path) or "(根)"
                errors.append(f"{file.relative_to(artifacts)} {where}: {err.message}")
    return errors
