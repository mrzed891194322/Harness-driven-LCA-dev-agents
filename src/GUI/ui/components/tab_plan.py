from __future__ import annotations

import gradio as gr

from functions.plan_editor import (
    EMPTY_PREVIEW,
    MAX_PLAN_INPUTS,
    PlanTemplateError,
    parse_execution_plan_template,
    render_plan_segments,
    render_plan_status,
    render_plan_toc,
)


def build_tab_plan() -> tuple[
    gr.Tab,
    list[gr.Markdown],
    gr.Markdown,
    gr.Markdown,
    gr.State,
    list[gr.Textbox],
    gr.Button,
    gr.UploadButton,
    gr.Button,
]:
    """Build the Markdown-template-driven structured execution-plan form."""
    import config

    try:
        template = parse_execution_plan_template(config.PLAN_INPUT_TEMPLATE_PATH)
        template_error = None
    except PlanTemplateError as exc:
        template = None
        template_error = str(exc)

    plan_inputs: list[gr.Textbox] = []
    plan_markdowns: list[gr.Markdown] = []
    plan_source_state = gr.State(
        value=template.source if template is not None else None
    )
    initial_segments = (
        render_plan_segments(template)
        if template is not None
        else (EMPTY_PREVIEW,)
    )
    with gr.Tab("计划制定", id="plan_editor_tab") as plan_tab:
        with gr.Column(
            elem_id="plan-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            with gr.Column(
                elem_id="plan-editor-panel",
                elem_classes=["inner-panel-grid"],
            ):
                plan_status = gr.Markdown(
                    (
                        f"⚠️ **计划模板不可用**：{template_error}"
                        if template_error
                        else render_plan_status(template, "默认模板")
                    ),
                    elem_id="plan-field-status",
                )

                with gr.Row(
                    elem_id="plan-editor-content-row",
                    elem_classes=["panel-content-row"],
                ):
                    with gr.Column(
                        scale=1,
                        min_width=170,
                        elem_id="plan-toc-column",
                        elem_classes=["plan-toc-column"],
                    ):
                        plan_toc = gr.Markdown(
                            render_plan_toc(template)
                            if template is not None
                            else "### 章节目录\n\n*模板不可用。*",
                            elem_id="plan-toc",
                        )

                    with gr.Column(
                        scale=3,
                        elem_id="plan-form-column",
                        elem_classes=["plan-form-column"],
                    ):
                        with gr.Column(
                            elem_id="plan-form-scroll",
                            elem_classes=["panel-scroll-container", "plan-form-scroll"],
                        ):
                            for index in range(MAX_PLAN_INPUTS):
                                plan_markdowns.append(
                                    gr.Markdown(
                                        (
                                            initial_segments[index]
                                            if index < len(initial_segments)
                                            else ""
                                        ),
                                        visible=index < len(initial_segments),
                                        elem_id=f"plan-markdown-{index + 1:02d}",
                                        elem_classes=["plan-static-markdown"],
                                    )
                                )
                                field_is_active = (
                                    template is not None
                                    and index < len(template.fields)
                                )
                                value = (
                                    template.values[index]
                                    if field_is_active
                                    else ""
                                )
                                plan_inputs.append(
                                    gr.Textbox(
                                        label=None,
                                        show_label=False,
                                        placeholder="请在此填写" if field_is_active else "",
                                        lines=4,
                                        max_lines=12,
                                        value=value,
                                        visible=field_is_active,
                                        interactive=True,
                                        container=False,
                                        elem_id=f"plan-input-{index + 1:02d}",
                                        elem_classes=["plan-form-input"],
                                    )
                                )
                            plan_markdowns.append(
                                gr.Markdown(
                                    (
                                        initial_segments[MAX_PLAN_INPUTS]
                                        if MAX_PLAN_INPUTS < len(initial_segments)
                                        else ""
                                    ),
                                    visible=MAX_PLAN_INPUTS < len(initial_segments),
                                    elem_id=f"plan-markdown-{MAX_PLAN_INPUTS + 1:02d}",
                                    elem_classes=["plan-static-markdown"],
                                )
                            )

                with gr.Row(
                    elem_id="plan-editor-actions-row",
                    elem_classes=["panel-actions-row"],
                ):
                    close_plan_btn = gr.Button(
                        "关闭面板",
                        variant="secondary",
                        elem_id="close-plan-btn",
                    )
                    upload_plan_btn = gr.UploadButton(
                        "上传计划",
                        file_types=[".md"],
                        variant="secondary",
                        elem_id="upload-plan-btn",
                    )
                    with gr.Column(
                        elem_id="execute-lca-button-wrap",
                        elem_classes=["plan-execute-tooltip"],
                        min_width=120,
                    ):
                        execute_lca_btn = gr.Button(
                            "执行LCA计划",
                            variant="primary",
                            interactive=False,
                            elem_id="execute-lca-plan-btn",
                        )

    return (
        plan_tab,
        plan_markdowns,
        plan_toc,
        plan_status,
        plan_source_state,
        plan_inputs,
        close_plan_btn,
        upload_plan_btn,
        execute_lca_btn,
    )
