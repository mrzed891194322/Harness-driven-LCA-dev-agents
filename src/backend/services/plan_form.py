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
template_version: 1
---

# LCA 执行计划

## 研究对象

<!-- 比较对象、情景与交付地点 -->

## 功能单位

<!-- 功能描述、数量和单位 -->

## 生命周期阶段

<!-- 纳入与排除的阶段 -->

## 附加条件

<!-- 研究目的、截断、分配、LCIA 方法、数据库和其他限制；没有则写「无」 -->

## 参考资料

<!-- 保存计划时由页面根据已上传文件填写 -->
"""


def parse_plan(text: str) -> PlanFields:
    """Read the four plan fields. Unrecognized Markdown becomes 附加条件."""
    sections = _h2_sections(text)
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
    for path in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
        if not _is_reference_file(path):
            continue
        rows.append(_reference_record(path, notes.get(path.name, "")))
    return rows


def save_reference(root: Path, filename: str, data: bytes) -> dict[str, object]:
    path = _reference_path(root, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".uploading")
    temporary.write_bytes(data)
    temporary.replace(path)
    return _reference_record(path, _read_notes(root).get(path.name, ""))


def save_reference_note(root: Path, filename: str, note: str) -> dict[str, object]:
    path = _reference_path(root, filename)
    if not path.is_file():
        raise FileNotFoundError(filename)
    notes = _read_notes(root)
    text = note.strip()
    if text:
        notes[path.name] = text
    else:
        notes.pop(path.name, None)
    _write_notes(root, notes)
    return _reference_record(path, notes.get(path.name, ""))


def delete_reference(root: Path, filename: str) -> None:
    path = _reference_path(root, filename)
    if not path.is_file():
        raise FileNotFoundError(filename)
    path.unlink()
    notes = _read_notes(root)
    if path.name in notes:
        notes.pop(path.name, None)
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


def _is_reference_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.is_symlink()
        and path.name.lower() != "readme.md"
        and not path.name.startswith(".")
    )


def _reference_record(path: Path, note: str) -> dict[str, object]:
    return {
        "name": path.name,
        "size": path.stat().st_size,
        "path": f"{INPUTS_RELATIVE.as_posix()}/{path.name}",
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


def _reference_path(root: Path, filename: str) -> Path:
    raw = filename or ""
    if not raw or "/" in raw or "\\" in raw or "\x00" in raw:
        raise PlanFormError("文件名无效")
    name = Path(raw).name
    if name in {".", ".."} or name.startswith("."):
        raise PlanFormError("文件名无效")
    if name.lower() == "readme.md":
        raise PlanFormError("不能覆盖说明文件")
    folder = inputs_dir(root).resolve()
    path = (folder / name).resolve()
    if path.parent != folder:
        raise PlanFormError("文件名无效")
    if path.is_symlink():
        raise PlanFormError("不能替换链接文件")
    return path


def _h2_sections(text: str) -> dict[str, str]:
    matches = list(_H2.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = _section_key(match.group(1))
        if key is None:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[key] = text[start:end]
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
