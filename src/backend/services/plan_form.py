"""LCA plan YAML (items list), template download, and reference uploads.

Schema principle: upload what you render.
- General item: {title, content}
- Special item (only two): {type: database|lcia, enable: bool, content?: str}
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.services.plan_templates import PlanTemplateError, get_plan_template

PLAN_RELATIVE = Path("workspace/artifacts/plan/main_plan.yaml")
REVISE_PLAN_RELATIVE = Path("workspace/artifacts/plan/revise_plan.yaml")
INPUTS_RELATIVE = Path("harness/knowledge/inputs")
TEMPLATE_NAME = "lca-plan-template.yaml"
PLAN_KIND = "lca_execution_plan"
PLAN_VERSION = 2
DEFAULT_TEMPLATE_ID = "full-lifecycle"
NOTES_NAME = "reference-notes.json"
REFERENCE_TYPES = frozenset({"knowledge", "bom", "lci"})
DEFAULT_REFERENCE_TYPE = "knowledge"
REFERENCE_STORAGE: dict[str, Path] = {
    "knowledge": INPUTS_RELATIVE,
    "bom": Path("harness/knowledge/uploads/bom"),
    "lci": Path("harness/knowledge/uploads/lci"),
}
RUN_REFERENCE_DEST: dict[str, Path] = {
    "bom": Path("bom/references"),
    "lci": Path("mapping/references"),
}
DEFAULT_WORKFLOW_NAME = "full-lca"
PLAN_BY_WORKFLOW = {"full-lca": PLAN_RELATIVE, "revise-lca": REVISE_PLAN_RELATIVE}
MAX_PLAN_BYTES = 2 * 1024 * 1024
UPLOAD_SUFFIXES = {".yaml", ".yml"}
SPECIAL_TYPES = frozenset({"database", "lcia"})
SPECIAL_TITLES = {"database": "LCA 数据库", "lcia": "LCIA 方法"}


class PlanFormError(ValueError):
    """Rejected plan or reference upload."""


class PlanFormConflict(PlanFormError):
    """Import refused because a plan already exists and overwrite is false."""


@dataclass(frozen=True)
class PlanItem:
    title: str = ""
    content: str = ""
    type: str = ""
    enable: bool = True

    @property
    def is_special(self) -> bool:
        return self.type in SPECIAL_TYPES

    def as_dict(self) -> dict[str, Any]:
        if self.is_special:
            row: dict[str, Any] = {"type": self.type, "enable": bool(self.enable)}
            if self.title.strip() and self.title.strip() != SPECIAL_TITLES.get(self.type, ""):
                row["title"] = self.title.strip()
            if self.content.strip() or self.type == "lcia":
                row["content"] = self.content
            return row
        return {"title": self.title, "content": self.content}


@dataclass(frozen=True)
class PlanDocument:
    items: tuple[PlanItem, ...]
    template_id: str = DEFAULT_TEMPLATE_ID

    def as_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id or DEFAULT_TEMPLATE_ID,
            "items": [item.as_dict() for item in self.items],
        }


# Backward-compatible alias used by a few call sites / tests.
PlanFields = PlanDocument


def empty_plan_document(template_id: str = DEFAULT_TEMPLATE_ID) -> PlanDocument:
    return PlanDocument(items=(), template_id=template_id or DEFAULT_TEMPLATE_ID)


def _section_plan_item(section_id: str) -> PlanItem | None:
    key = (section_id or "").strip()
    if key == "study-sec-subject":
        return PlanItem(title="研究对象", content="")
    if key == "study-sec-basis":
        return PlanItem(title="计算基准（功能单位）", content="")
    if key == "study-sec-life":
        return PlanItem(title="生命周期范围", content="")
    if key == "study-sec-place":
        return PlanItem(title="地域与时间", content="")
    if key == "study-sec-database":
        return PlanItem(type="database", enable=True, title=SPECIAL_TITLES["database"])
    if key == "study-sec-lcia":
        return PlanItem(type="lcia", enable=True, title=SPECIAL_TITLES["lcia"], content="")
    if key == "study-sec-impact":
        return PlanItem(title="关注的环境影响", content="")
    if key == "study-sec-special":
        return PlanItem(title="特殊要求", content="")
    return None


def items_for_template(root: Path, template_id: str) -> tuple[PlanItem, ...]:
    """Plan item skeleton from harness/plan-templates sections (download + empty plan)."""
    tid = (template_id or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID
    try:
        detail = get_plan_template(root, tid)
    except PlanTemplateError:
        detail = get_plan_template(root, DEFAULT_TEMPLATE_ID)
    items: list[PlanItem] = []
    for section in detail.get("sections") or []:
        if not isinstance(section, dict):
            continue
        item = _section_plan_item(str(section.get("id") or ""))
        if item is not None:
            items.append(item)
    if not items:
        if tid != DEFAULT_TEMPLATE_ID:
            return items_for_template(root, DEFAULT_TEMPLATE_ID)
        return (
            PlanItem(title="研究对象", content=""),
            PlanItem(title="计算基准（功能单位）", content=""),
            PlanItem(title="生命周期范围", content=""),
            PlanItem(title="地域与时间", content=""),
            PlanItem(type="database", enable=True, title=SPECIAL_TITLES["database"]),
            PlanItem(type="lcia", enable=True, title=SPECIAL_TITLES["lcia"], content=""),
            PlanItem(title="关注的环境影响", content=""),
            PlanItem(title="特殊要求", content=""),
        )
    return tuple(items)


def default_items(
    template_id: str = DEFAULT_TEMPLATE_ID,
    *,
    root: Path | None = None,
) -> tuple[PlanItem, ...]:
    """Same skeleton as the download template for the given plan type."""
    if root is not None:
        return items_for_template(root, template_id)
    return items_for_template(Path.cwd(), template_id)


def template_download_filename(template_id: str = DEFAULT_TEMPLATE_ID) -> str:
    tid = (template_id or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID
    return f"lca-plan-{tid}.yaml"


def try_parse_item(raw: Any, *, index: int) -> PlanItem | None:
    """Return a PlanItem when raw matches schema; None when this entry is illegal."""
    if not isinstance(raw, dict):
        return None
    type_name = str(raw.get("type") or "").strip().lower()
    if type_name:
        if type_name not in SPECIAL_TYPES:
            return None
        if "enable" not in raw:
            return None
        enable = raw.get("enable")
        if not isinstance(enable, bool):
            return None
        # Special items must not look like a general title/content-only row with junk keys only.
        title = str(raw.get("title") or SPECIAL_TITLES[type_name]).strip() or SPECIAL_TITLES[type_name]
        content = raw.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, (str, int, float)):
            return None
        return PlanItem(title=title, content=str(content), type=type_name, enable=enable)

    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    if "content" not in raw:
        return None
    content = raw.get("content")
    if content is None:
        content = ""
    if not isinstance(content, (str, int, float)):
        return None
    return PlanItem(title=title, content=str(content), type="", enable=True)


def parse_item(raw: Any, *, index: int) -> PlanItem:
    item = try_parse_item(raw, index=index)
    if item is None:
        if not isinstance(raw, dict):
            raise PlanFormError(f"计划 YAML 无效：items[{index}] 必须是对象")
        type_name = str(raw.get("type") or "").strip().lower()
        if type_name and type_name not in SPECIAL_TYPES:
            raise PlanFormError(
                f"计划 YAML 无效：items[{index}].type 只能是 database 或 lcia，收到「{type_name}」"
            )
        if type_name:
            raise PlanFormError(
                f"计划 YAML 无效：items[{index}]（type={type_name}）须有 enable: true/false"
            )
        raise PlanFormError(f"计划 YAML 无效：items[{index}] 一般项须有合法 title 与 content")
    return item


def parse_items(raw_items: Any, *, require_valid: bool) -> list[PlanItem]:
    """Parse items.

    require_valid=True (upload): any illegal entry fails the whole document —
    do not half-load dirty data.
    require_valid=False (soft read / save sanitize): keep only legal entries.
    """
    if raw_items is None:
        if require_valid:
            raise PlanFormError("计划 YAML 无效：缺少 items 列表")
        return []
    if not isinstance(raw_items, list):
        if require_valid:
            raise PlanFormError("计划 YAML 无效：items 必须是列表")
        return []
    if require_valid and len(raw_items) == 0:
        raise PlanFormError("计划 YAML 无效：items 不能为空")

    if require_valid:
        # Fail-fast on the first illegal fragment so the UI never renders a partial dirty set.
        return [parse_item(raw, index=index) for index, raw in enumerate(raw_items)]

    kept: list[PlanItem] = []
    for index, raw in enumerate(raw_items):
        item = try_parse_item(raw, index=index)
        if item is not None:
            kept.append(item)
    return kept


def template_yaml(template_id: str = DEFAULT_TEMPLATE_ID, *, root: Path) -> str:
    tid = (template_id or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID
    doc = PlanDocument(items=items_for_template(root, tid), template_id=tid)
    return render_plan(doc)


def template_markdown(*, root: Path) -> str:
    return template_yaml(root=root)


def parse_plan_meta(text: str) -> dict[str, Any]:
    data = _load_plan_yaml(text)
    if not isinstance(data, dict):
        return {"template_id": DEFAULT_TEMPLATE_ID}
    tid = str(data.get("template_id") or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID
    return {"template_id": tid, "kind": data.get("kind") or PLAN_KIND, "version": data.get("version") or PLAN_VERSION}


def parse_plan(text: str) -> PlanDocument:
    """Parse YAML plan into a PlanDocument (legacy fields → items when needed)."""
    doc = _document_from_yaml(text, require_valid=False)
    if doc is not None:
        return doc
    return empty_plan_document()


def render_plan(
    document: PlanDocument | dict[str, Any],
    reference_names: list[str] | None = None,
    *,
    template_id: str | None = None,
) -> str:
    """Serialize plan YAML. Main structure is items only (no references key)."""
    del reference_names  # references live under harness/knowledge/inputs, not in plan YAML
    doc = _coerce_document(document, template_id=template_id)
    payload: dict[str, Any] = {
        "kind": PLAN_KIND,
        "version": PLAN_VERSION,
        "template_id": doc.template_id,
        "items": [item.as_dict() for item in doc.items],
    }
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False)


def _coerce_document(
    document: PlanDocument | dict[str, Any],
    *,
    template_id: str | None = None,
) -> PlanDocument:
    """Keep only schema-legal items for save / start payloads."""
    if isinstance(document, PlanDocument):
        tid = (template_id or document.template_id or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID
        # Re-validate dataclass items through dict round-trip to drop anything illegal.
        items = parse_items([item.as_dict() for item in document.items], require_valid=False)
        return PlanDocument(items=tuple(items), template_id=tid)
    if isinstance(document, dict):
        tid = (
            template_id
            or str(document.get("template_id") or DEFAULT_TEMPLATE_ID)
        ).strip() or DEFAULT_TEMPLATE_ID
        items = parse_items(document.get("items"), require_valid=False)
        if not items and document.get("fields"):
            items = _legacy_fields_to_items(document.get("fields"))
        return PlanDocument(items=tuple(items), template_id=tid)
    raise PlanFormError("计划无效")


def _load_plan_yaml(text: str) -> Any:
    if not (text or "").strip():
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def _document_from_yaml(text: str, *, require_valid: bool) -> PlanDocument | None:
    stripped = (text or "").strip()
    if not stripped:
        if require_valid:
            raise PlanFormError("计划 YAML 为空")
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        if require_valid:
            raise PlanFormError(f"计划 YAML 无法解析：{exc}") from exc
        return None
    if data is None:
        if require_valid:
            raise PlanFormError("计划 YAML 为空")
        return None
    if not isinstance(data, dict):
        if require_valid:
            raise PlanFormError("计划 YAML 无效：根节点必须是对象")
        return None

    tid = str(data.get("template_id") or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID

    if "items" in data:
        items = parse_items(data.get("items"), require_valid=require_valid)
        return PlanDocument(items=tuple(items), template_id=tid)

    # Legacy: fields: {subject, ...} → items
    fields = data.get("fields")
    if isinstance(fields, dict):
        items = _legacy_fields_to_items(fields)
        if require_valid and not items:
            raise PlanFormError("计划 YAML 无效：缺少 items（或旧版 fields）")
        return PlanDocument(items=tuple(items), template_id=tid)

    if require_valid:
        raise PlanFormError("计划 YAML 无效：缺少 items 列表（一般项 title/content；特殊项 type+enable）")
    return None


def _legacy_fields_to_items(fields: Any) -> list[PlanItem]:
    if not isinstance(fields, dict):
        return []
    items: list[PlanItem] = []

    def add_text(title: str, key: str) -> None:
        value = str(fields.get(key) or "").strip()
        items.append(PlanItem(title=title, content=value))

    add_text("研究对象", "subject")
    add_text("计算基准（功能单位）", "functional_unit")
    add_text("生命周期范围", "life_cycle_stages")
    place = str(fields.get("place") or "").strip()
    if not place:
        conditions = str(fields.get("conditions") or "")
        for block in conditions.split("\n\n"):
            text = block.strip()
            if text.startswith("地域与时间"):
                place = text.split("：", 1)[-1].split(":", 1)[-1].strip()
                break
    items.append(PlanItem(title="地域与时间", content=place))
    items.append(
        PlanItem(
            type="database",
            enable=True,
            title=SPECIAL_TITLES["database"],
            content=str(fields.get("database") or ""),
        )
    )
    items.append(
        PlanItem(
            type="lcia",
            enable=True,
            title=SPECIAL_TITLES["lcia"],
            content=str(fields.get("lcia") or ""),
        )
    )
    add_text("关注的环境影响", "impacts")
    special = str(fields.get("special") or "").strip()
    if not special:
        # leftover conditions blocks without known labels
        special = ""
    items.append(PlanItem(title="特殊要求", content=special))
    return items


def plan_relative_path(root: Path, *, workflow: str | None = None) -> Path:
    del root
    key = (workflow or DEFAULT_WORKFLOW_NAME).strip() or DEFAULT_WORKFLOW_NAME
    if key not in PLAN_BY_WORKFLOW:
        raise PlanFormError(f"未知工作流：{key}")
    return PLAN_BY_WORKFLOW[key]


def plan_path(root: Path, *, workflow: str | None = None) -> Path:
    return root / plan_relative_path(root, workflow=workflow)


def inputs_dir(root: Path) -> Path:
    return root / INPUTS_RELATIVE


def read_plan_document(root: Path, *, workflow: str | None = None) -> dict[str, object]:
    relative = plan_relative_path(root, workflow=workflow)
    path = root / relative
    if not path.is_file():
        doc = PlanDocument(
            items=default_items(DEFAULT_TEMPLATE_ID, root=root),
            template_id=DEFAULT_TEMPLATE_ID,
        )
        content = ""
    else:
        content = path.read_text(encoding="utf-8")
        doc = parse_plan(content)
        if not doc.items:
            doc = PlanDocument(
                items=default_items(doc.template_id, root=root),
                template_id=doc.template_id,
            )
    references = list_references(root)
    return {
        "path": relative.as_posix(),
        "content": content,
        "fields": doc.as_dict(),
        "template_id": doc.template_id,
        "items": [item.as_dict() for item in doc.items],
        "references": references,
    }


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def save_plan(
    root: Path,
    document: PlanDocument | dict[str, Any],
    *,
    workflow: str | None = None,
    template_id: str | None = None,
) -> None:
    path = plan_path(root, workflow=workflow)
    names = [item["name"] for item in list_references(root)]
    write_text_atomic(path, render_plan(document, names, template_id=template_id))


def import_plan_bytes(
    root: Path,
    *,
    workflow: str | None,
    filename: str,
    data: bytes,
    overwrite: bool = False,
) -> dict[str, object]:
    text = _decode_plan_upload(filename, data)
    doc = _document_from_yaml(text, require_valid=True)
    assert doc is not None
    relative = plan_relative_path(root, workflow=workflow)
    path = root / relative
    names = [item["name"] for item in list_references(root)]
    rendered = render_plan(doc, names)
    if path.is_file() and not overwrite:
        existing = path.read_text(encoding="utf-8")
        if existing.strip() and existing != rendered and existing != text:
            raise PlanFormConflict("计划文件已存在；如需覆盖请设置 overwrite=true")
    write_text_atomic(path, rendered)
    return {
        "path": relative.as_posix(),
        "fields": doc.as_dict(),
        "template_id": doc.template_id,
        "items": [item.as_dict() for item in doc.items],
        "content": rendered,
        "filename": Path(filename or "").name,
    }


def normalize_reference_type(value: str | None) -> str:
    key = (value or "").strip().lower()
    if key in REFERENCE_TYPES:
        return key
    return DEFAULT_REFERENCE_TYPE


def list_references(root: Path) -> list[dict[str, object]]:
    notes = _read_notes(root)
    rows: list[dict[str, object]] = []
    for ref_type in sorted(REFERENCE_TYPES):
        folder = _storage_dir(root, ref_type)
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*"), key=lambda item: item.as_posix().lower()):
            if not _is_reference_file(folder, path):
                continue
            relative = path.relative_to(folder).as_posix()
            note_key = _note_key(ref_type, relative)
            rows.append(
                _reference_record(
                    path,
                    relative,
                    notes.get(note_key, notes.get(relative, "") if ref_type == "knowledge" else ""),
                    ref_type,
                )
            )
    return rows


def save_reference(root: Path, filename: str, data: bytes, *, ref_type: str = DEFAULT_REFERENCE_TYPE) -> dict[str, object]:
    saved = save_references(root, [(filename, data)], [ref_type])
    return saved[0]


def save_references(
    root: Path,
    uploads: list[tuple[str, bytes]],
    types: list[str] | None = None,
) -> list[dict[str, object]]:
    prepared: list[tuple[Path, str, str, bytes]] = []
    seen: set[str] = set()
    conflicts: list[str] = []
    for index, (filename, data) in enumerate(uploads):
        ref_type = normalize_reference_type(types[index] if types and index < len(types) else None)
        path = _reference_path(root, filename, ref_type=ref_type)
        folder = _storage_dir(root, ref_type).resolve()
        relative = path.relative_to(folder).as_posix()
        token = f"{ref_type}:{relative}"
        if token in seen or path.exists() or _reference_exists(root, relative, exclude_type=None):
            conflicts.append(relative)
            continue
        seen.add(token)
        prepared.append((path, relative, ref_type, data))
    if conflicts:
        names = "、".join(f"「{name}」" for name in dict.fromkeys(conflicts))
        raise PlanFormError(f"不能上传同名文件：{names}")
    saved: list[dict[str, object]] = []
    notes = _read_notes(root)
    for path, relative, ref_type, data in prepared:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".uploading")
        temporary.write_bytes(data)
        temporary.replace(path)
        note_key = _note_key(ref_type, relative)
        saved.append(_reference_record(path, relative, notes.get(note_key, ""), ref_type))
    return saved


def save_reference_note(root: Path, filename: str, note: str, *, ref_type: str | None = None) -> dict[str, object]:
    located = _locate_reference(root, filename, ref_type=ref_type)
    if located is None:
        raise FileNotFoundError(filename)
    ref_type, path, relative = located
    notes = _read_notes(root)
    note_key = _note_key(ref_type, relative)
    text = note.strip()
    if text:
        notes[note_key] = text
    else:
        notes.pop(note_key, None)
        if ref_type == "knowledge":
            notes.pop(relative, None)
    _write_notes(root, notes)
    return _reference_record(path, relative, notes.get(note_key, ""), ref_type)


def save_reference_type(root: Path, filename: str, ref_type: str, *, current_type: str | None = None) -> dict[str, object]:
    target = normalize_reference_type(ref_type)
    located = _locate_reference(root, filename, ref_type=current_type)
    if located is None:
        raise FileNotFoundError(filename)
    current, path, relative = located
    if current == target:
        notes = _read_notes(root)
        note_key = _note_key(current, relative)
        return _reference_record(path, relative, notes.get(note_key, ""), current)
    dest = _reference_path(root, relative, ref_type=target)
    if dest.exists():
        raise PlanFormError(f"不能改为「{target}」：目标位置已有同名文件")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))
    folder = _storage_dir(root, current)
    _prune_empty_dirs(folder, path.parent)
    notes = _read_notes(root)
    old_key = _note_key(current, relative)
    note = notes.pop(old_key, None)
    if current == "knowledge":
        note = notes.pop(relative, note)
    if note:
        notes[_note_key(target, relative)] = note
    _write_notes(root, notes)
    return _reference_record(dest, relative, notes.get(_note_key(target, relative), ""), target)


def apply_reference_types(root: Path, items: list[dict[str, Any]]) -> None:
    for row in items:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        target = normalize_reference_type(str(row.get("type") or ""))
        located = _locate_reference(root, name)
        if located is None:
            continue
        current, _, _ = located
        if current != target:
            save_reference_type(root, name, target, current_type=current)


def stage_references_for_run(root: Path, workspace: Path) -> dict[str, list[str]]:
    """After workspace artifacts reset: copy BOM/LCI uploads into artifact reference dirs."""
    staged: dict[str, list[str]] = {"bom": [], "lci": []}
    art = workspace / "artifacts"
    for ref_type in ("bom", "lci"):
        src_root = _storage_dir(root, ref_type)
        dest_root = art / RUN_REFERENCE_DEST[ref_type]
        if not src_root.is_dir():
            continue
        for path in sorted(src_root.rglob("*"), key=lambda item: item.as_posix().lower()):
            if not _is_reference_file(src_root, path):
                continue
            relative = path.relative_to(src_root)
            target = dest_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            staged[ref_type].append(relative.as_posix())
    return staged


def delete_reference(root: Path, filename: str, *, ref_type: str | None = None) -> None:
    located = _locate_reference(root, filename, ref_type=ref_type)
    if located is None:
        raise FileNotFoundError(filename)
    ref_type, path, relative = located
    folder = _storage_dir(root, ref_type).resolve()
    path.unlink()
    _prune_empty_dirs(folder, path.parent)
    notes = _read_notes(root)
    note_key = _note_key(ref_type, relative)
    if note_key in notes:
        notes.pop(note_key, None)
    if ref_type == "knowledge" and relative in notes:
        notes.pop(relative, None)
    _write_notes(root, notes)


def _decode_plan_upload(filename: str, data: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in UPLOAD_SUFFIXES:
        raise PlanFormError("请上传 .yaml / .yml 计划文档")
    if len(data) > MAX_PLAN_BYTES:
        raise PlanFormError("计划 YAML 超过 2MB")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PlanFormError("文件不是 UTF-8 文本") from exc


def decode_plan_upload(filename: str, data: bytes) -> PlanDocument:
    text = _decode_plan_upload(filename, data)
    doc = _document_from_yaml(text, require_valid=True)
    assert doc is not None
    return doc


def _is_reference_file(folder: Path, path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        relative = path.relative_to(folder)
    except ValueError:
        return False
    if relative.as_posix().lower() in {"readme.md", NOTES_NAME}:
        return False
    return not any(part.startswith(".") for part in relative.parts)


def _reference_record(path: Path, relative: str, note: str, ref_type: str) -> dict[str, object]:
    storage = REFERENCE_STORAGE[ref_type]
    return {
        "name": relative,
        "type": ref_type,
        "size": path.stat().st_size,
        "path": f"{storage.as_posix()}/{relative}",
        "note": note,
    }


def _note_key(ref_type: str, relative: str) -> str:
    if ref_type == DEFAULT_REFERENCE_TYPE:
        return relative
    return f"{ref_type}/{relative}"


def _storage_dir(root: Path, ref_type: str) -> Path:
    rel = REFERENCE_STORAGE.get(normalize_reference_type(ref_type), INPUTS_RELATIVE)
    return root / rel


def _reference_exists(root: Path, relative: str, *, exclude_type: str | None) -> bool:
    for ref_type in REFERENCE_TYPES:
        if exclude_type and ref_type == exclude_type:
            continue
        path = _storage_dir(root, ref_type) / relative
        if path.is_file():
            return True
    return False


def _locate_reference(root: Path, filename: str, *, ref_type: str | None = None) -> tuple[str, Path, str] | None:
    if ref_type:
        path = _reference_path(root, filename, ref_type=normalize_reference_type(ref_type))
        if not path.is_file():
            return None
        folder = _storage_dir(root, normalize_reference_type(ref_type)).resolve()
        return normalize_reference_type(ref_type), path, path.relative_to(folder).as_posix()
    relative = _reference_relative(filename)
    for candidate in REFERENCE_TYPES:
        folder = _storage_dir(root, candidate).resolve()
        path = folder / relative
        if path.is_file():
            return candidate, path.resolve(), relative
    return None


def _notes_path(root: Path) -> Path:
    return inputs_dir(root) / NOTES_NAME


def _parse_notes(path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(name): text
        for name, text in payload.items()
        if isinstance(name, str) and isinstance(text, str)
    }


def _read_notes(root: Path) -> dict[str, str]:
    return _parse_notes(_notes_path(root)) or {}


def _write_notes(root: Path, notes: dict[str, str]) -> None:
    folder = inputs_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    _notes_path(root).write_text(
        json.dumps(notes, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _reference_relative(filename: str) -> str:
    raw = (filename or "").replace("\\", "/").strip()
    if not raw or "\x00" in raw:
        raise PlanFormError("文件名无效")
    parts: list[str] = []
    for part in raw.split("/"):
        if part in {"", "."}:
            continue
        if part == ".." or part.startswith("."):
            raise PlanFormError("文件名无效")
        parts.append(part)
    if not parts:
        raise PlanFormError("文件名无效")
    if len(parts) == 1 and parts[0].lower() == "readme.md":
        raise PlanFormError("不能覆盖说明文件")
    if len(parts) == 1 and parts[0] == NOTES_NAME:
        raise PlanFormError("不能覆盖注释文件")
    return "/".join(parts)


def _reference_path(root: Path, filename: str, *, ref_type: str = DEFAULT_REFERENCE_TYPE) -> Path:
    relative = _reference_relative(filename)
    folder = _storage_dir(root, ref_type).resolve()
    cursor = folder
    for part in relative.split("/"):
        cursor = cursor / part
        if cursor.is_symlink():
            raise PlanFormError("不能替换链接文件")
        if cursor.is_file() and part != relative.split("/")[-1]:
            raise PlanFormError("文件名无效")
    path = cursor.resolve()
    if folder not in path.parents:
        raise PlanFormError("文件名无效")
    if path.is_symlink():
        raise PlanFormError("不能替换链接文件")
    return path


def _prune_empty_dirs(folder: Path, directory: Path) -> None:
    current = directory
    while current != folder:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
