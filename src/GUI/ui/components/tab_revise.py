from __future__ import annotations

import gradio as gr

from ui.components.render_mdfile import (
    MarkdownDocumentView,
    build_markdown_document_view,
)


def build_tab_revise() -> tuple[
    gr.Tab,
    MarkdownDocumentView,
    gr.Button,
    gr.UploadButton,
    gr.Button,
]:
    """Build the independent in-memory LCA assessment improvement form."""
    import config

    with gr.Tab(
        "LCA评估修改面板(功能开发中)",
        id="lca_improvement_tab",
    ) as improvement_tab:
        with gr.Column(
            elem_id="improvement-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            with gr.Column(
                elem_id="improvement-editor-panel",
                elem_classes=["inner-panel-grid"],
            ):
                view = build_markdown_document_view(
                    template_path=config.REVISE_TEMPLATE_PATH,
                    component_prefix="improvement",
                    template_label="改进模板",
                    document_label="改进方案",
                    heading_levels=(1, 2),
                    toc_title="章节目录",
                )

                with gr.Row(
                    elem_id="improvement-editor-actions-row",
                    elem_classes=["panel-actions-row"],
                ):
                    close_improvement_btn = gr.Button(
                        "关闭面板",
                        variant="secondary",
                        elem_id="close-improvement-btn",
                    )
                    upload_improvement_btn = gr.UploadButton(
                        "上传改进方案",
                        file_types=[".md"],
                        variant="secondary",
                        elem_id="upload-improvement-btn",
                    )
                    execute_improvement_btn = gr.Button(
                        "执行改进",
                        variant="primary",
                        interactive=False,
                        elem_id="execute-improvement-btn",
                    )

    return (
        improvement_tab,
        view,
        close_improvement_btn,
        upload_improvement_btn,
        execute_improvement_btn,
    )
