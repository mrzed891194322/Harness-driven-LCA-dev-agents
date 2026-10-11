"""Structured LCA plan fields, Markdown template, and reference uploads."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PLAN_RELATIVE = Path("harness/knowledge/plan/main_plan.md")
INPUTS_RELATIVE = Path("harness/knowledge/inputs")
TEMPLATE_NAME = "lca-plan-template.md"
NOTES_NAME = ".reference-notes.json"
MAX_PLAN_BYTES = 2 * 1024 * 1024
PLAN_SUFFIXES = {".md", ".markdown", ".txt"}
FIELD_KEYS = ("研究对象", "功能单位", "生命周期阶段", "附加条件")
_SKIP_LABELS = {"研究对象", "功能单位", "生命周期阶段", "参考资料"}
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n*", re.DOTALL)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_SECTION_TITLE = re.compile(r"^section\s+(\d+)\b", re.IGNORECASE)
_BOLD = re.compile(r"^-\s+\*\*(.+?)\*\*\s*[：:]\s*(.*)$", re.MULTILINE)


class PlanFormError(ValueError):
    """Rejected plan or reference upload."""


@dataclass(frozen=True)
class PlanFields:
    subject: str
    functional_unit: str
    life_cycle_stages: str
    conditions: str

    def as_dict(self) -> dict[str, str]:
        return {
            "subject": self.subject,
            "functional_unit": self.functional_unit,
            "life_cycle_stages": self.life_cycle_stages,
            "conditions": self.conditions,
        }


def template_markdown() -> str:
    return """---
template_kind: lca_execution_plan
template_version: 2
---

# LCA 执行计划

## section 1

<!--
研究对象 / Study object
请在本注释之后自行填写。有多个对象时，每个对象单独成段。
Write your own content below this comment. Put each object in its own paragraph.
-->

## section 2

<!--
计算基准（功能单位）/ Functional unit
请在本注释之后填写文字，这些文字会进入「附加说明」。数量和单位请到界面填写。
Write the note below this comment. It is placed in the note field. Enter the quantity and unit in the interface.
-->

## section 3

<!--
生命周期范围 / Life cycle scope
请在本注释之后填写文字，这些文字会进入「附加说明」。纳入哪些阶段请到界面选择。
Write the note below this comment. It is placed in the note field. Select the stages in the interface.
-->

## section 4

<!--
地域与时间 / Geography and time
请在本注释之后自行填写，文字会进入同一个文本框。
Write below this comment. The text goes into one text box.
-->

## section 5

<!--
LCA 数据库 / LCA database
用户不能填写，请到界面手动选择。
Do not fill this section. Select it manually in the interface.
-->

## section 6

<!--
环境影响评价方法（LCIA）/ LCIA method
用户不能填写，请到界面手动选择。
Do not fill this section. Select it manually in the interface.
-->

## section 7

<!--
关注的环境影响 / Impact categories
用户不能填写，请到界面手动选择。
Do not fill this section. Select it manually in the interface.
-->

## section 8

<!--
特殊要求 / Special requirements
请在本注释之后自行填写。没有额外限制时写「无」。
Write any extra requirements below this comment. Write "none" if there are none.
-->
"""


def parse_plan(text: str) -> PlanFields:
    """Read the four plan fields. Unrecognized Markdown becomes 附加条件."""
    sections = _h2_sections(text)
    numbered = _numbered_sections(text)
    if numbered is not None and not any(key in sections for key in FIELD_KEYS):
        return _fields_from_numbered(numbered)
    if any(key in sections for key in FIELD_KEYS):
        return PlanFields(
            subject=_clean(sections.get("研究对象", "")),
            functional_unit=_clean(sections.get("功能单位", "")),
            life_cycle_stages=_clean(sections.get("生命周期阶段", "")),
            conditions=_clean(sections.get("附加条件", "")),
        )

    labeled = _bold_values(text)
    if any(labeled.get(key) for key in ("研究对象", "功能单位", "生命周期阶段")):
        return PlanFields(
            subject=labeled.get("研究对象", ""),
            functional_unit=labeled.get("功能单位", ""),
            life_cycle_stages=labeled.get("生命周期阶段", ""),
            conditions=_legacy_conditions(text),
        )

    body = _clean(_FRONTMATTER.sub("", text))
    if not body or body == "# LCA 执行计划":
        return PlanFields("", "", "", "")
    return PlanFields("", "", "", body)


def render_plan(fields: PlanFields, reference_names: list[str]) -> str:
    names = [name for name in reference_names if name.strip()]
    if names:
        ref_lines = "\n".join(f"- `harness/knowledge/inputs/{name}`" for name in names)
    else:
        ref_lines = "- 未上传。请在计划页的参考资料区上传文件后再保存。"
    conditions = fields.conditions.strip() or "无"
    return (
        "---\n"
        "template_kind: lca_execution_plan\n"
        "template_version: 1\n"
        "---\n\n"
        "# LCA 执行计划\n\n"
        "## 研究对象\n\n"
        f"{fields.subject.strip()}\n\n"
        "## 功能单位\n\n"
        f"{fields.functional_unit.strip()}\n\n"
        "## 生命周期阶段\n\n"
        f"{fields.life_cycle_stages.strip()}\n\n"
        "## 附加条件\n\n"
        f"{conditions}\n\n"
        "## 参考资料\n\n"
        f"{ref_lines}\n"
        "- Agent 仅可使用上述用户上传资料、项目已有知识库和活动 openLCA 数据库，"
        "禁止联网搜索或使用其他来源。\n"
    )


def plan_path(root: Path) -> Path:
    return root / PLAN_RELATIVE


def inputs_dir(root: Path) -> Path:
    return root / INPUTS_RELATIVE


def read_plan_document(root: Path) -> dict[str, object]:
    path = plan_path(root)
    if not path.is_file():
        fields = PlanFields("", "", "", "")
        content = ""
    else:
        content = path.read_text(encoding="utf-8")
        fields = parse_plan(content)
    references = list_references(root)
    return {
        "path": PLAN_RELATIVE.as_posix(),
        "content": content,
        "fields": fields.as_dict(),
        "references": references,
    }


def save_plan(root: Path, fields: PlanFields) -> None:
    path = plan_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    names = [item["name"] for item in list_references(root)]
    path.write_text(render_plan(fields, names), encoding="utf-8")


def list_references(root: Path) -> list[dict[str, object]]:
    folder = inputs_dir(root)
    if not folder.is_dir():
        return []
    notes = _read_notes(root)
    rows: list[dict[str, object]] = []
    for path in sorted(folder.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not _is_reference_file(folder, path):
            continue
        relative = path.relative_to(folder).as_posix()
        rows.append(_reference_record(path, relative, notes.get(relative, "")))
    return rows


def save_reference(root: Path, filename: str, data: bytes) -> dict[str, object]:
    saved = save_references(root, [(filename, data)])
    return saved[0]


def save_references(root: Path, uploads: list[tuple[str, bytes]]) -> list[dict[str, object]]:
    folder = inputs_dir(root).resolve()
    prepared: list[tuple[Path, str, bytes]] = []
    seen: set[str] = set()
    conflicts: list[str] = []
    for filename, data in uploads:
        path = _reference_path(root, filename)
        relative = path.relative_to(folder).as_posix()
        if relative in seen or path.exists():
            conflicts.append(relative)
            continue
        seen.add(relative)
        prepared.append((path, relative, data))
    if conflicts:
        names = "、".join(f"「{name}」" for name in dict.fromkeys(conflicts))
        raise PlanFormError(f"不能上传同名文件：{names}")
    saved: list[dict[str, object]] = []
    notes = _read_notes(root)
    for path, relative, data in prepared:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".uploading")
        temporary.write_bytes(data)
        temporary.replace(path)
        saved.append(_reference_record(path, relative, notes.get(relative, "")))
    return saved


def save_reference_note(root: Path, filename: str, note: str) -> dict[str, object]:
    path = _reference_path(root, filename)
    if not path.is_file():
        raise FileNotFoundError(filename)
    relative = path.relative_to(inputs_dir(root).resolve()).as_posix()
    notes = _read_notes(root)
    text = note.strip()
    if text:
        notes[relative] = text
    else:
        notes.pop(relative, None)
    _write_notes(root, notes)
    return _reference_record(path, relative, notes.get(relative, ""))


def delete_reference(root: Path, filename: str) -> None:
    folder = inputs_dir(root).resolve()
    path = _reference_path(root, filename)
    if not path.is_file():
        raise FileNotFoundError(filename)
    relative = path.relative_to(folder).as_posix()
    path.unlink()
    _prune_empty_dirs(folder, path.parent)
    notes = _read_notes(root)
    if relative in notes:
        notes.pop(relative, None)
        _write_notes(root, notes)


def decode_plan_upload(filename: str, data: bytes) -> PlanFields:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in PLAN_SUFFIXES:
        raise PlanFormError("请上传 .md 文档")
    if len(data) > MAX_PLAN_BYTES:
        raise PlanFormError("Markdown 超过 2MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PlanFormError("文件不是 UTF-8 文本") from exc
    return parse_plan(text)


def _is_reference_file(folder: Path, path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        relative = path.relative_to(folder)
    except ValueError:
        return False
    if relative.as_posix().lower() == "readme.md":
        return False
    return not any(part.startswith(".") for part in relative.parts)


def _reference_record(path: Path, relative: str, note: str) -> dict[str, object]:
    return {
        "name": relative,
        "size": path.stat().st_size,
        "path": f"{INPUTS_RELATIVE.as_posix()}/{relative}",
        "note": note,
    }


def _notes_path(root: Path) -> Path:
    return inputs_dir(root) / NOTES_NAME


def _read_notes(root: Path) -> dict[str, str]:
    path = _notes_path(root)
    if not path.is_file():
        return {}
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
    return "/".join(parts)


def _reference_path(root: Path, filename: str) -> Path:
    relative = _reference_relative(filename)
    folder = inputs_dir(root).resolve()
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


def _numbered_sections(text: str) -> dict[int, str] | None:
    """Bodies under ``## section N``. None when the file does not use that outline."""
    matches = list(_H2.finditer(text))
    sections: dict[int, str] = {}
    found = False
    for index, match in enumerate(matches):
        number = _SECTION_TITLE.match(match.group(1).strip())
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if number is None:
            continue
        found = True
        sections[int(number.group(1))] = text[start:end]
    return sections if found else None


def _fields_from_numbered(sections: dict[int, str]) -> PlanFields:
    """Map the v2 worksheet onto the saved fields.

    Written text lands in text boxes. Sections 2 and 3 also have selectable
    controls, so their whole body stays in ``附加说明`` and does not set those
    controls. Sections 5–7 are chosen in the interface.
    """
    blocks = _place_blocks(sections.get(4, ""))
    special = _clean(sections.get(8, ""))
    if special and special not in {"无", "none", "None"}:
        blocks.append(special)
    return PlanFields(
        subject=_clean(sections.get(1, "")),
        functional_unit=_as_note(sections.get(2, "")),
        life_cycle_stages=_as_note(sections.get(3, "")),
        conditions="\n\n".join(blocks),
    )


def _as_note(text: str) -> str:
    """Keep a template body in 附加说明, even if it mentions 数量 or 阶段."""
    body = _clean(text)
    if not body:
        return ""
    return f"附加说明：{body}"


def _place_blocks(text: str) -> list[str]:
    """Section 4 is one text box. Keep the body together, including old labels."""
    body = _clean(text)
    if not body:
        return []
    return [f"地域与时间：{body}"]


def _h2_sections(text: str) -> dict[str, str]:
    """Split by the known H2 fields; unknown H2 sections belong to 附加条件.

    Users often write their own ``## 1. 研究目的…`` headings inside 附加条件; those
    used to end the section, so the conditions were lost on the next load (#18).
    """
    matches = list(_H2.finditer(text))
    sections: dict[str, str] = {}
    extra: list[str] = []
    for index, match in enumerate(matches):
        key = _section_key(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if key is None:
            extra.append(match.group(0) + text[start:end])
        elif key not in sections:
            sections[key] = text[start:end]
    if extra and any(key in sections for key in FIELD_KEYS):
        base = sections.get("附加条件", "").rstrip()
        sections["附加条件"] = "\n\n".join(part for part in (base, *extra) if part.strip())
    return sections


def _section_key(title: str) -> str | None:
    cleaned = re.sub(r"^\d+\.\s*", "", title).strip()
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", cleaned).strip()
    for key in (*FIELD_KEYS, "参考资料"):
        if cleaned == key or cleaned.startswith(key):
            return key
    if "参考文献" in cleaned:
        return "参考资料"
    return None


def _bold_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in _BOLD.finditer(text):
        key = _section_key(match.group(1))
        if key in FIELD_KEYS and key not in values:
            values[key] = match.group(2).strip()
    return values


def _legacy_conditions(text: str) -> str:
    kept: list[str] = []
    for raw in _FRONTMATTER.sub("", text).splitlines():
        line = raw.strip()
        if not line or line.startswith("# ") or line.startswith(">"):
            continue
        if line.startswith("## "):
            key = _section_key(line[3:].strip())
            if key in {"研究对象", "功能单位", "生命周期阶段", "参考资料"}:
                continue
            kept.append(raw)
            continue
        label = _BOLD.match(raw.strip())
        if label is not None:
            key = _section_key(label.group(1))
            if key in _SKIP_LABELS:
                continue
        kept.append(raw)
    return _clean("\n".join(kept))


def _clean(text: str) -> str:
    without_comments = _COMMENT.sub("", text)
    lines = [line.rstrip() for line in without_comments.splitlines()]
    compact: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if compact and not blank:
                compact.append("")
            blank = True
            continue
        compact.append(line)
        blank = False
    return "\n".join(compact).strip()
