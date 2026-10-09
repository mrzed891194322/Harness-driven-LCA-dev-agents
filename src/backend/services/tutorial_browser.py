"""Read-only catalog of Markdown tutorials under docs/tutorial."""

from __future__ import annotations

from pathlib import Path

_TEXT_SUFFIXES = {".md"}
_GROUP_LABELS = {
    "": "概览",
    "basics": "入门",
    "panel": "控制面板",
    "workflow": "工作流",
}
_GROUP_ORDER = ["", "basics", "panel", "workflow"]


class TutorialPathError(ValueError):
    pass


def tutorial_catalog(project: Path) -> dict:
    root = _tutorial_root(project)
    if not root.is_dir():
        return {"groups": []}

    buckets: dict[str, list[dict[str, str]]] = {}
    for path in _collect(root):
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        parts = path.relative_to(root).parts
        group_id = parts[0] if len(parts) > 1 else ""
        rest = parts[1:] if group_id else parts
        buckets.setdefault(group_id, []).append(
            {"path": rel, "label": _entry_label(rest, path)}
        )

    def sort_key(group_id: str) -> tuple:
        if group_id in _GROUP_ORDER:
            return (0, _GROUP_ORDER.index(group_id))
        return (1, group_id)

    groups = []
    for group_id in sorted(buckets, key=sort_key):
        entries = sorted(
            buckets[group_id],
            key=lambda item: (item["path"] != "README.md", item["path"]),
        )
        groups.append(
            {
                "id": group_id or "overview",
                "label": _GROUP_LABELS.get(group_id, group_id),
                "entries": entries,
            }
        )
    return {"groups": groups}


def read_tutorial_document(project: Path, relative: str) -> dict:
    path = _resolve_document(project, relative)
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise TutorialPathError("document is not utf-8 text") from exc
    root = _tutorial_root(project).resolve()
    rel = path.resolve().relative_to(root).as_posix()
    label = _file_label(path.name)
    return {
        "path": rel,
        "label": label,
        "title": _document_title(path, content, label),
        "kind": "markdown",
        "content": content,
    }


def first_tutorial_path(project: Path) -> str | None:
    catalog = tutorial_catalog(project)
    for group in catalog["groups"]:
        if group["entries"]:
            return group["entries"][0]["path"]
    return None


def _tutorial_root(project: Path) -> Path:
    return project / "docs" / "tutorial"


def _collect(root: Path) -> list[Path]:
    resolved_root = root.resolve()
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if not path.resolve().is_relative_to(resolved_root):
            continue
        found.append(path)
    return sorted(found, key=lambda path: path.relative_to(root).as_posix())


def _resolve_document(project: Path, relative: str) -> Path:
    root = _tutorial_root(project).resolve()
    if not relative or relative.startswith(("/", "\\")) or "\\" in relative:
        raise TutorialPathError("invalid tutorial path")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise TutorialPathError("invalid tutorial path")
    if candidate.suffix.lower() not in _TEXT_SUFFIXES:
        raise TutorialPathError("unsupported tutorial document")
    if not candidate.is_file():
        raise FileNotFoundError(relative)
    return candidate


def _file_label(name: str) -> str:
    lowered = name.lower()
    if lowered == "readme.md":
        return "教程首页"
    if lowered.endswith(".md"):
        return name[: -len(".md")]
    return Path(name).stem


def _entry_label(parts: tuple[str, ...], path: Path) -> str:
    *dirs, filename = parts
    if path.suffix.lower() == ".md":
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            content = ""
        title = _document_title(path, content, "")
        if title:
            return title
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
