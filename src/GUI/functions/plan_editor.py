"""Marker-preserving helpers for the GUI plan form.

The plan tab always starts from ``ui/assets/template/plan.md``. A valid
uploaded document may replace that in-memory source, but the staged document
is only written to ``workspace/inputs/plan.md`` when execution starts.

Editable regions use one deliberately small grammar::

    <!-- PLAN_TEXTBOX -->
    ---
    ***✍️ 用户填写内容区***

    ---

Only ``PLAN_TEXTBOX`` decides whether the region becomes a textbox. Everything
outside a marked region remains ordinary Markdown and is preserved verbatim.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from functions.utils.file_loader.private_utils.template_metadata import (
    PLAN_TEMPLATE_KIND,
    PLAN_TEMPLATE_VERSION,
    split_front_matter,
)
from functions.utils.file_loader.private_utils.value_handler import read_text_robust

MAX_PLAN_INPUTS = 20
EMPTY_PREVIEW = "*请填写或上传 LCA 执行计划。*"
PLAN_TEXTBOX_MARKER = "<!-- PLAN_TEXTBOX -->"


class PlanTemplateError(ValueError):
    """Raised when an execution-plan document or marker is malformed."""


@dataclass(frozen=True)
class PlanInputField:
    field_id: str
    label: str = ""
    placeholder: str = "请在此填写"
    rows: int = 4
    section: int = 0

    @property
    def id(self) -> str:
        return self.field_id


@dataclass(frozen=True)
class PlanMarkdownPart:
    content: str


@dataclass(frozen=True)
class PlanInputPart:
    field: PlanInputField
    prefix: str
    suffix: str
    syntax: str = "textbox"


PlanPart = PlanMarkdownPart | PlanInputPart


@dataclass(frozen=True)
class PlanTemplate:
    path: Path
    metadata: dict[str, str]
    parts: tuple[PlanPart, ...]
    fields: tuple[PlanInputField, ...]
    values: tuple[str, ...]
    body: str
    front_matter: str
    source: str


_PLAN_TEXTBOX = re.compile(
    r"(?m)"
    r"^(?P<indent>[ \t]*)<!--\s*PLAN_TEXTBOX\s*-->[ \t]*\n"
    r"(?P=indent)---[ \t]*\n"
    r"(?P=indent)\*{2,3}\s*✍\ufe0f?\s*用户填写内容区\s*\*{2,3}[ \t]*\n"
    r"(?P<value>.*?)"
    r"^(?P=indent)---[ \t]*(?=\n|$)",
    re.DOTALL,
)
_PLAN_TEXTBOX_MARKER = re.compile(r"<!--\s*PLAN_TEXTBOX\s*-->")
_UNSUPPORTED_PLAN_INPUT = re.compile(r"<!--\s*/?PLAN_INPUT\b")
_TOC_HEADING = re.compile(r"(?m)^(?P<hashes>#{1,2})\s+(?P<title>.+?)\s*$")


def _parse_body(
    body: str,
    *,
    path: Path,
) -> tuple[tuple[PlanPart, ...], tuple[PlanInputField, ...], tuple[str, ...]]:
    if _UNSUPPORTED_PLAN_INPUT.search(body):
        raise PlanTemplateError(
            "不再支持 `PLAN_INPUT` 注释格式；请改用 `<!-- PLAN_TEXTBOX -->` "
            "及其后的“用户填写内容区”区块。"
        )

    matches = list(_PLAN_TEXTBOX.finditer(body))
    if len(matches) > MAX_PLAN_INPUTS:
        raise PlanTemplateError(
            f"计划包含 {len(matches)} 个可编辑区域，超过上限 {MAX_PLAN_INPUTS}。"
        )

    parts: list[PlanPart] = []
    fields: list[PlanInputField] = []
    values: list[str] = []
    cursor = 0

    def read_value(match: re.Match[str]) -> str:
        lines = match.group("value").splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        indent = match.group("indent")
        value = "\n".join(
            line[len(indent) :] if indent and line.startswith(indent) else line
            for line in lines
        )
        return "" if value.casefold() == "none" else value

    for position, match in enumerate(matches, start=1):
        static_content = body[cursor : match.start()]
        if _PLAN_TEXTBOX_MARKER.search(static_content):
            raise PlanTemplateError(
                f"模板 `{path}` 包含未连接完整“用户填写内容区”的 "
                "`PLAN_TEXTBOX` 标记。"
            )
        if _PLAN_TEXTBOX_MARKER.search(match.group("value")):
            raise PlanTemplateError(
                f"模板 `{path}` 的第 {position} 个 `PLAN_TEXTBOX` "
                "缺少闭合分隔线。"
            )
        parts.append(PlanMarkdownPart(static_content))

        field = PlanInputField(field_id=f"textbox_{position:02d}")
        value_start = match.start("value")
        value_end = match.end("value")
        parts.append(
            PlanInputPart(
                field=field,
                prefix=body[match.start() : value_start],
                suffix=body[value_end : match.end()],
            )
        )
        fields.append(field)
        values.append(read_value(match))
        cursor = match.end()

    trailing_content = body[cursor:]
    if _PLAN_TEXTBOX_MARKER.search(trailing_content):
        raise PlanTemplateError(
            f"模板 `{path}` 包含未连接完整“用户填写内容区”的 "
            "`PLAN_TEXTBOX` 标记。"
        )
    parts.append(PlanMarkdownPart(trailing_content))
    return tuple(parts), tuple(fields), tuple(values)


def _read_marked_document(
    text: str,
    *,
    path: Path,
) -> tuple[
    dict[str, str],
    str,
    tuple[PlanPart, ...],
    tuple[PlanInputField, ...],
    tuple[str, ...],
    str,
    str,
]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    metadata, body = split_front_matter(normalized)
    if metadata.get("template_kind") != PLAN_TEMPLATE_KIND:
        raise PlanTemplateError(
            "计划 YAML front matter 必须包含 `template_kind: lca_plan_input`。"
        )
    if metadata.get("template_version") != PLAN_TEMPLATE_VERSION:
        raise PlanTemplateError(
            "计划 YAML front matter 必须包含 `template_version: 1`。"
        )
    parts, fields, values = _parse_body(body, path=path)
    front_matter = normalized[: len(normalized) - len(body)] if body else normalized
    return metadata, body, parts, fields, values, front_matter, normalized


def parse_execution_plan_text(
    text: str,
    *,
    source: Path | str = "<staged-plan.md>",
) -> PlanTemplate:
    """Parse a staged plan without reading or writing the workspace plan."""
    path = Path(source)
    metadata, body, parts, fields, values, front_matter, normalized = (
        _read_marked_document(text, path=path)
    )
    return PlanTemplate(
        path=path,
        metadata=dict(metadata),
        parts=parts,
        fields=fields,
        values=values,
        body=body,
        front_matter=front_matter,
        source=normalized,
    )


def parse_execution_plan_template(filepath: Path | str) -> PlanTemplate:
    """Parse a Markdown plan template and its optional textbox regions."""
    path = Path(filepath)
    if not path.is_file():
        raise PlanTemplateError(f"模板文件不存在：`{path}`。")
    try:
        source = read_text_robust(path)
    except OSError as exc:
        raise PlanTemplateError(f"无法读取模板 `{path}`：{exc}") from exc
    return parse_execution_plan_text(source, source=path)


parse_plan_template = parse_execution_plan_template


def _markdown_parts(template: PlanTemplate) -> tuple[PlanMarkdownPart, ...]:
    return tuple(
        part for part in template.parts if isinstance(part, PlanMarkdownPart)
    )


def render_template_parts(template: PlanTemplate) -> tuple[PlanPart, ...]:
    """Return the original alternating Markdown and textbox document parts."""
    return template.parts


def render_plan_segments(template: PlanTemplate) -> tuple[str, ...]:
    """Return Markdown around each textbox, adding only invisible TOC anchors."""
    heading_index = 0

    def add_anchor(match: re.Match[str]) -> str:
        nonlocal heading_index
        heading_index += 1
        return (
            f'<a id="plan-heading-{heading_index}"></a>\n\n'
            f'{match.group("hashes")} {match.group("title")}'
        )

    return tuple(
        _TOC_HEADING.sub(add_anchor, part.content)
        for part in _markdown_parts(template)
    )


def render_plan_markdown(template: PlanTemplate) -> str:
    """Compatibility helper returning the staged plan's static Markdown."""
    rendered = "".join(render_plan_segments(template)).strip()
    return rendered or EMPTY_PREVIEW


def render_plan_toc(template: PlanTemplate) -> str:
    """Build a two-level directory from complete ``#`` and ``##`` titles."""
    headings: list[tuple[int, str]] = []
    for part in _markdown_parts(template):
        headings.extend(
            (len(match.group("hashes")), match.group("title").strip())
            for match in _TOC_HEADING.finditer(part.content)
        )
    if not headings:
        return "### 章节目录\n\n*模板未声明一级或二级标题。*"

    lines = ["### 章节目录", ""]
    for index, (level, title) in enumerate(headings, start=1):
        indent = "  " if level == 2 else ""
        lines.append(f"{indent}- [{title}](#plan-heading-{index})")
    return "\n".join(lines)


def render_plan_status(template: PlanTemplate, source_label: str) -> str:
    count = len(template.fields)
    if count:
        return (
            f"✅ 已加载{source_label}；检测到 **{count}** 个原位输入区域"
            f"（上限 {MAX_PLAN_INPUTS}）。"
        )
    return f"✅ 已加载{source_label}；该计划没有输入标记，将按只读 Markdown 保存。"


def extract_plan_values(
    template: PlanTemplate | Path | str,
    plan_text: str,
) -> list[str]:
    """Read marked values by position, padding missing values with blanks."""
    parsed = (
        template
        if isinstance(template, PlanTemplate)
        else parse_execution_plan_template(template)
    )
    _, _, _, _, source_values, _, _ = _read_marked_document(
        plan_text,
        path=Path("<uploaded-plan.md>"),
    )
    values = list(source_values[: len(parsed.fields)])
    values.extend("" for _ in range(len(parsed.fields) - len(values)))
    return values


load_plan_values = extract_plan_values
import_plan_values = extract_plan_values


def load_plan_form(
    plan_path: Path,
    default_template_path: Path,
) -> tuple[PlanTemplate, list[str]]:
    """Load only the default template; ``plan_path`` is intentionally ignored."""
    del plan_path
    template = parse_execution_plan_template(default_template_path)
    return template, list(template.values)


def load_plan_text(plan_path: Path, default_template_path: Path) -> str:
    """Read only the default template; ``plan_path`` is intentionally ignored."""
    del plan_path
    return read_text_robust(default_template_path)


def _values_by_field(
    template: PlanTemplate,
    values: Mapping[str, Any] | Sequence[Any],
) -> dict[str, str]:
    if isinstance(values, Mapping):
        return {
            field.field_id: (
                ""
                if values.get(field.field_id) is None
                else str(values[field.field_id])
            )
            for field in template.fields
        }
    sequence = list(values)
    return {
        field.field_id: (
            ""
            if index >= len(sequence) or sequence[index] is None
            else str(sequence[index])
        )
        for index, field in enumerate(template.fields)
    }


def _normalized_value(value: Any) -> str:
    text = (
        ""
        if value is None
        else str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    )
    return "" if text.casefold() == "none" else text


def _value_for_part(part: PlanInputPart, value: Any) -> str:
    text = _normalized_value(value)
    indent_match = re.match(r"(?m)^(?P<indent>[ \t]*)<!--", part.prefix)
    indent = indent_match.group("indent") if indent_match else ""
    if text:
        indented = "\n".join(
            f"{indent}{line}" if line else ""
            for line in text.splitlines()
        )
        value_region = f"\n{indented}\n\n"
    else:
        value_region = "\n"
    return f"{part.prefix}{value_region}{part.suffix}"


def serialize_execution_plan(
    template: PlanTemplate | Path | str,
    values: Mapping[str, Any] | Sequence[Any],
) -> str:
    """Replace textbox values while preserving all marker and Markdown text."""
    parsed = (
        template
        if isinstance(template, PlanTemplate)
        else parse_execution_plan_template(template)
    )
    value_map = _values_by_field(parsed, values)
    chunks: list[str] = []
    for part in parsed.parts:
        if isinstance(part, PlanMarkdownPart):
            chunks.append(part.content)
        else:
            chunks.append(
                _value_for_part(part, value_map[part.field.field_id])
            )
    return f"{parsed.front_matter}{''.join(chunks)}"


serialize_plan = serialize_execution_plan


def render_plan_preview(text: str | None) -> str:
    """Return the plan body without YAML front matter."""
    normalized = text or ""
    if not normalized.strip():
        return EMPTY_PREVIEW
    _, body = split_front_matter(normalized)
    return body.strip() or EMPTY_PREVIEW


def is_plan_ready(values: str | Mapping[str, Any] | Sequence[Any] | None) -> bool:
    if values is None:
        return False
    if isinstance(values, str):
        return bool(values.strip())
    if isinstance(values, Mapping):
        return any(value is not None and str(value).strip() for value in values.values())
    return any(value is not None and str(value).strip() for value in values)


def read_uploaded_plan(file_obj: Any) -> str:
    if file_obj is None:
        raise ValueError("未选择任何计划文件。")
    if isinstance(file_obj, (str, os.PathLike)):
        raw_path = file_obj
    else:
        raw_path = getattr(file_obj, "path", None) or getattr(
            file_obj,
            "name",
            file_obj,
        )
    uploaded_path = Path(raw_path)
    if uploaded_path.suffix.lower() != ".md":
        raise ValueError("仅支持上传 Markdown（.md）计划文件。")
    if not uploaded_path.is_file():
        raise ValueError("上传的计划文件不存在或无法读取。")
    return read_text_robust(uploaded_path)


def validate_execution_plan(text: str | None) -> None:
    if not text or not text.strip():
        raise ValueError("计划内容不能为空。")
    try:
        _read_marked_document(text, path=Path("<plan.md>"))
    except PlanTemplateError as exc:
        raise ValueError(str(exc)) from exc


def save_execution_plan(
    text: str | None = None,
    target_path: Path | None = None,
    *,
    template: PlanTemplate | Path | str | None = None,
    template_path: Path | None = None,
    values: Mapping[str, Any] | Sequence[Any] | None = None,
) -> Path:
    if target_path is None:
        raise ValueError("必须提供执行计划保存路径。")
    if values is not None:
        source_template = template or template_path
        if source_template is None:
            raise ValueError("结构化计划保存必须提供模板路径。")
        text = serialize_execution_plan(source_template, values)
    if text is None:
        raise ValueError("计划内容不能为空。")
    validate_execution_plan(text)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.",
        suffix=".tmp",
        dir=target_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary_path, target_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return target_path


def save_structured_plan(
    template: PlanTemplate | Path | str,
    values: Mapping[str, Any] | Sequence[Any],
    target_path: Path,
) -> Path:
    return save_execution_plan(
        target_path=target_path,
        template=template,
        values=values,
    )
