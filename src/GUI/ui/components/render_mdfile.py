"""Render Markdown tabs with shared left navigation and dynamic input areas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gradio as gr

from functions.plan_editor import (
    MAX_PLAN_INPUTS,
    MarkdownDocument,
    PlanTemplateError,
    parse_markdown_document_file,
    parse_markdown_document_text,
    render_document_segments,
    render_document_status,
    render_document_toc,
)


@dataclass
class MarkdownDocumentView:
    component_prefix: str
    document_label: str
    template_label: str
    heading_levels: tuple[int, ...]
    toc_title: str
    status_heading: str
    show_load_status: bool
    content_row: gr.Row
    markdowns: list[gr.Markdown]
    toc: gr.Markdown
    status: gr.Markdown
    source_state: gr.State
    inputs: list[gr.Textbox]


def _status_text(status_heading: str, detail: str = "") -> str:
    return "\n\n".join(
        part for part in (status_heading.strip(), detail.strip()) if part
    )


def build_markdown_document_view(
    *,
    component_prefix: str,
    document_label: str,
    template_label: str | None = None,
    template_path: Path | None = None,
    initial_source: str | None = None,
    heading_levels: tuple[int, ...] = (1, 2),
    toc_title: str = "章节目录",
    status_heading: str = "",
    show_load_status: bool = True,
    content_visible: bool = True,
) -> MarkdownDocumentView:
    """Build an independent document view with an optional textbox pool."""
    if template_path is not None and initial_source is not None:
        raise ValueError("Markdown 视图不能同时指定模板路径和初始文本。")

    resolved_template_label = template_label or document_label
    document: MarkdownDocument | None = None
    template_error: str | None = None
    try:
        if template_path is not None:
            document = parse_markdown_document_file(template_path)
        elif initial_source is not None:
            document = parse_markdown_document_text(
                initial_source,
                source=f"<{component_prefix}-initial.md>",
            )
    except PlanTemplateError as exc:
        template_error = str(exc)

    anchor_prefix = f"{component_prefix}-heading"
    source_state = gr.State(
        value=document.source if document is not None else None
    )
    initial_segments = (
        render_document_segments(
            document,
            anchor_prefix=anchor_prefix,
            heading_levels=heading_levels,
        )
        if document is not None
        else ()
    )
    if template_error:
        status_detail = (
            f"⚠️ **{resolved_template_label}不可用**：{template_error}"
        )
    elif document is not None and show_load_status:
        status_detail = render_document_status(
            document,
            "默认模板",
        )
    else:
        status_detail = ""
    status = gr.Markdown(
        _status_text(status_heading, status_detail),
        elem_id=f"{component_prefix}-field-status",
    )

    markdowns: list[gr.Markdown] = []
    inputs: list[gr.Textbox] = []
    with gr.Row(
        visible=content_visible,
        elem_id=f"{component_prefix}-content-row",
        elem_classes=["panel-content-row"],
    ) as content_row:
        with gr.Column(
            scale=1,
            min_width=170,
            elem_id=f"{component_prefix}-toc-column",
            elem_classes=["markdown-document-toc-column"],
        ):
            toc = gr.Markdown(
                (
                    render_document_toc(
                        document,
                        anchor_prefix=anchor_prefix,
                        heading_levels=heading_levels,
                        title=toc_title,
                    )
                    if document is not None
                    else f"### {toc_title}\n\n*尚未加载文档。*"
                ),
                elem_id=f"{component_prefix}-toc",
            )

        with gr.Column(
            scale=3,
            elem_id=f"{component_prefix}-document-column",
            elem_classes=["markdown-document-column"],
        ):
            with gr.Column(
                elem_id=f"{component_prefix}-document-scroll",
                elem_classes=[
                    "panel-scroll-container",
                    "markdown-document-scroll",
                ],
            ):
                for index in range(MAX_PLAN_INPUTS):
                    markdowns.append(
                        gr.Markdown(
                            (
                                initial_segments[index]
                                if index < len(initial_segments)
                                else ""
                            ),
                            visible=index < len(initial_segments),
                            elem_id=(
                                f"{component_prefix}-markdown-{index + 1:02d}"
                            ),
                            elem_classes=["markdown-document-segment"],
                        )
                    )
                    field_is_active = (
                        document is not None
                        and index < len(document.fields)
                    )
                    inputs.append(
                        gr.Textbox(
                            label=None,
                            show_label=False,
                            placeholder="请在此填写" if field_is_active else "",
                            lines=4,
                            max_lines=12,
                            value=(
                                document.values[index]
                                if field_is_active
                                else ""
                            ),
                            visible=field_is_active,
                            interactive=True,
                            container=False,
                            elem_id=f"{component_prefix}-input-{index + 1:02d}",
                            elem_classes=["markdown-document-input"],
                        )
                    )
                markdowns.append(
                    gr.Markdown(
                        (
                            initial_segments[MAX_PLAN_INPUTS]
                            if MAX_PLAN_INPUTS < len(initial_segments)
                            else ""
                        ),
                        visible=MAX_PLAN_INPUTS < len(initial_segments),
                        elem_id=(
                            f"{component_prefix}-markdown-"
                            f"{MAX_PLAN_INPUTS + 1:02d}"
                        ),
                        elem_classes=["markdown-document-segment"],
                    )
                )

    return MarkdownDocumentView(
        component_prefix=component_prefix,
        document_label=document_label,
        template_label=resolved_template_label,
        heading_levels=heading_levels,
        toc_title=toc_title,
        status_heading=status_heading,
        show_load_status=show_load_status,
        content_row=content_row,
        markdowns=markdowns,
        toc=toc,
        status=status,
        source_state=source_state,
        inputs=inputs,
    )


def document_output_components(view: MarkdownDocumentView) -> list:
    """Return components in the stable order used by all document events."""
    return [
        *view.markdowns,
        view.toc,
        view.status,
        *view.inputs,
        view.source_state,
    ]


def validate_document_view_pool(view: MarkdownDocumentView) -> None:
    if len(view.inputs) != MAX_PLAN_INPUTS:
        raise ValueError(
            f"{view.document_label}输入框池必须包含 "
            f"{MAX_PLAN_INPUTS} 个组件。"
        )
    if len(view.markdowns) != MAX_PLAN_INPUTS + 1:
        raise ValueError(
            f"{view.document_label} Markdown 片段池必须包含 "
            f"{MAX_PLAN_INPUTS + 1} 个组件。"
        )


def loaded_document_outputs(
    view: MarkdownDocumentView,
    document: MarkdownDocument,
    *,
    source_label: str | None = None,
) -> tuple:
    """Render one parsed document into an existing independent view."""
    segments = render_document_segments(
        document,
        anchor_prefix=f"{view.component_prefix}-heading",
        heading_levels=view.heading_levels,
    )
    markdown_updates = [
        gr.update(
            value=segments[index] if index < len(segments) else "",
            visible=index < len(segments),
        )
        for index in range(MAX_PLAN_INPUTS + 1)
    ]
    field_updates = [
        (
            gr.update(
                value=document.values[index],
                visible=True,
                placeholder="请在此填写",
                lines=4,
                max_lines=12,
                interactive=True,
            )
            if index < len(document.fields)
            else gr.update(
                value="",
                visible=False,
                placeholder="",
                lines=4,
                max_lines=12,
            )
        )
        for index in range(MAX_PLAN_INPUTS)
    ]
    if view.show_load_status:
        if not source_label:
            raise ValueError(
                f"{view.document_label}启用加载状态时必须提供来源标签。"
            )
        status_detail = render_document_status(
            document,
            source_label,
        )
    else:
        status_detail = ""
    return (
        *markdown_updates,
        render_document_toc(
            document,
            anchor_prefix=f"{view.component_prefix}-heading",
            heading_levels=view.heading_levels,
            title=view.toc_title,
        ),
        _status_text(view.status_heading, status_detail),
        *field_updates,
        document.source,
    )


def cleared_document_outputs(
    view: MarkdownDocumentView,
    *,
    toc_message: str = "尚未加载文档。",
) -> tuple:
    """Clear a view without changing its wrapper's warning components."""
    markdown_updates = [
        gr.update(value="", visible=False)
        for _ in range(MAX_PLAN_INPUTS + 1)
    ]
    hidden_fields = [
        gr.update(value="", visible=False)
        for _ in range(MAX_PLAN_INPUTS)
    ]
    return (
        *markdown_updates,
        f"### {view.toc_title}\n\n*{toc_message}*",
        view.status_heading,
        *hidden_fields,
        None,
    )


def unavailable_document_outputs(
    view: MarkdownDocumentView,
    message: str,
) -> tuple:
    """Clear a view and expose a document-specific load error in its status."""
    outputs = list(cleared_document_outputs(view, toc_message="文档不可用。"))
    status_index = MAX_PLAN_INPUTS + 2
    outputs[status_index] = _status_text(
        view.status_heading,
        f"⚠️ **{view.template_label}不可用**：{message}",
    )
    return tuple(outputs)
