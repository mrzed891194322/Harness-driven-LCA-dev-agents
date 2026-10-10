"""Read-only catalog of harness rules, specs, and related documents."""

from __future__ import annotations

from pathlib import Path

_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json"}
_SECTION_SPECS: tuple[tuple[str, str, set[str]], ...] = (
    ("rules", "规则", {".md", ".yaml", ".yml"}),
    ("specs", "规格", {".md", ".yaml", ".yml", ".json"}),
    ("workflows", "工作流", {".yaml", ".yml"}),
    ("knowledge", "知识", {".md", ".yaml", ".yml"}),
)
_GROUP_LABELS = {
    "": "概览",
    "project": "项目",
    "permissions": "权限规则",
    "deliverables": "交付物 schema",
    "examples": "示例",
    "lca": "LCA",
    "stages": "阶段",
    "assignments": "角色",
    "tools": "工具",
    "plan": "计划",
    "inputs": "输入",
    "shared": "共享",
}
_GROUP_ORDER = {
    "rules": ["", "project", "lca", "tools", "stages"],
    "workflows": [""],
    "knowledge": ["", "plan", "inputs"],
}


class HarnessPathError(ValueError):
    pass


def harness_catalog(project: Path) -> dict:
    root = project / "harness"
    sections = []
    for section_id, label, suffixes in _SECTION_SPECS:
        groups = _groups_for(root, section_id, suffixes)
        if groups:
            sections.append({"id": section_id, "label": label, "groups": groups})
    return {"sections": sections}


def read_harness_document(project: Path, relative: str) -> dict:
    path = _resolve_document(project, relative)
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HarnessPathError("document is not utf-8 text") from exc
    root = (project / "harness").resolve()
    rel = path.resolve().relative_to(root).as_posix()
    label = _file_label(path.name)
    return {
        "path": rel,
        "label": label,
        "title": _document_title(path, content, label),
        "kind": _kind(path),
        "content": content,
    }


def _groups_for(root: Path, section_id: str, suffixes: set[str]) -> list[dict]:
    buckets: dict[str, list[dict[str, str]]] = {}
    for path in _collect(root, section_id, suffixes):
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        if section_id == "workflows":
            group_id = ""
            label = _file_label(path.name)
        else:
            parts = path.relative_to(root / section_id).parts
            group_id = parts[0] if len(parts) > 1 else ""
            rest = parts[1:] if group_id else parts
            label = _entry_label(rest)
        buckets.setdefault(group_id, []).append({"path": rel, "label": label})

    order = _GROUP_ORDER.get(section_id, [])

    def sort_key(group_id: str) -> tuple:
        if group_id in order:
            return (0, order.index(group_id))
        return (1, group_id)

    groups = []
    for group_id in sorted(buckets, key=sort_key):
        entries = sorted(buckets[group_id], key=lambda item: (item["label"] != "说明", item["label"]))
        groups.append(
            {
                "id": group_id or "overview",
                "label": _GROUP_LABELS.get(group_id, group_id),
                "entries": entries,
            }
        )
    return groups


def _collect(root: Path, section_id: str, suffixes: set[str]) -> list[Path]:
    if not root.is_dir():
        return []
    resolved_root = root.resolve()
    if section_id == "workflows":
        found = [
            path
            for path in root.iterdir()
            if path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower() in suffixes
            and path.resolve().is_relative_to(resolved_root)
        ]
        return sorted(found, key=lambda path: path.name)
    base = root / section_id
    if not base.is_dir():
        return []
    found = []
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        relative = path.relative_to(base)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if not path.resolve().is_relative_to(resolved_root):
            continue
        found.append(path)
    return sorted(found, key=lambda path: path.relative_to(base).as_posix())


def _resolve_document(project: Path, relative: str) -> Path:
    root = (project / "harness").resolve()
    if not relative or relative.startswith(("/", "\\")) or "\\" in relative:
        raise HarnessPathError("invalid harness path")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise HarnessPathError("invalid harness path")
    if candidate.suffix.lower() not in _TEXT_SUFFIXES:
        raise HarnessPathError("unsupported harness document")
    if not candidate.is_file():
        raise FileNotFoundError(relative)
    return candidate


def _file_label(name: str) -> str:
    lowered = name.lower()
    if lowered == "readme.md":
        return "说明"
    for suffix in (".schema.json", ".md", ".yaml", ".yml", ".json"):
        if lowered.endswith(suffix):
            return name[: -len(suffix)]
    return Path(name).stem


def _entry_label(parts: tuple[str, ...]) -> str:
    *dirs, filename = parts
    label = _file_label(filename)
    if dirs:
        return " / ".join((*dirs, label))
    return label


def _document_title(path: Path, content: str, fallback: str) -> str:
    if path.suffix.lower() != ".md":
        return fallback
    for line in content.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title
    return fallback


def _kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "markdown"
    if suffix == ".json":
        return "json"
    return "yaml"
