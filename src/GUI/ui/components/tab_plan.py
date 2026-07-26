from __future__ import annotations

import gradio as gr

from ui.components.render_mdfile import (
    MarkdownDocumentView,
    build_markdown_document_view,
)


def build_tab_plan() -> tuple[
    gr.Tab,
    MarkdownDocumentView,
    gr.Button,
    gr.UploadButton,
    gr.Button,
]:
    """Build the Markdown-template-driven structured execution-plan form."""
    import config

    with gr.Tab("计划制定", id="plan_editor_tab") as plan_tab:
        with gr.Column(
            elem_id="plan-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            with gr.Column(
                elem_id="plan-editor-panel",
                elem_classes=["inner-panel-grid"],
            ):
                view = build_markdown_document_view(
                    template_path=config.PLAN_INPUT_TEMPLATE_PATH,
                    component_prefix="plan",
                    template_label="计划模板",
                    document_label="计划",
                    heading_levels=(1, 2),
                    toc_title="章节目录",
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
        view,
        close_plan_btn,
        upload_plan_btn,
        execute_lca_btn,
    )
