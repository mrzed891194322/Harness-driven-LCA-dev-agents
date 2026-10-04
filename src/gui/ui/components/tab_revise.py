from __future__ import annotations

import gradio as gr

from gui.i18n import t
from gui.ui.components.render_mdfile import (
    MarkdownDocumentView,
    build_markdown_document_view,
)


def build_tab_revise(
    locale: str,
) -> tuple[
    gr.Tab,
    MarkdownDocumentView,
    gr.Button,
    gr.UploadButton,
    gr.Button,
]:
    """Build the independent in-memory LCA assessment improvement form."""
    from gui import config

    with gr.Tab(
        t("tab.improvement", locale),
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
                    template_label=t("revise.template_label", locale),
                    document_label=t("revise.document_label", locale),
                    heading_levels=(1, 2),
                    toc_title=t("plan.toc_title", locale),
                    locale=locale,
                )

                with gr.Row(
                    elem_id="improvement-editor-actions-row",
                    elem_classes=["panel-actions-row"],
                ):
                    close_improvement_btn = gr.Button(
                        t("plan.close", locale),
                        variant="secondary",
                        elem_id="close-improvement-btn",
                    )
                    upload_improvement_btn = gr.UploadButton(
                        t("revise.upload", locale),
                        file_types=[".md"],
                        variant="secondary",
                        elem_id="upload-improvement-btn",
                    )
                    execute_improvement_btn = gr.Button(
                        t("revise.execute", locale),
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
