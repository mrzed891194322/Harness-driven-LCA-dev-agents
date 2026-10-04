from __future__ import annotations

import gradio as gr

from gui.i18n import t
from gui.ui.components.render_mdfile import (
    MarkdownDocumentView,
    build_markdown_document_view,
)


def build_tab_plan(
    locale: str,
) -> tuple[
    gr.Tab,
    MarkdownDocumentView,
    gr.Button,
    gr.UploadButton,
    gr.Button,
]:
    """Build the Markdown-template-driven structured execution-plan form."""
    from gui import config

    with gr.Tab(t("tab.plan", locale), id="plan_editor_tab") as plan_tab:
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
                    template_label=t("plan.template_label", locale),
                    document_label=t("plan.document_label", locale),
                    heading_levels=(1, 2),
                    toc_title=t("plan.toc_title", locale),
                    locale=locale,
                )

                with gr.Row(
                    elem_id="plan-editor-actions-row",
                    elem_classes=["panel-actions-row"],
                ):
                    close_plan_btn = gr.Button(
                        t("plan.close", locale),
                        variant="secondary",
                        elem_id="close-plan-btn",
                    )
                    upload_plan_btn = gr.UploadButton(
                        t("plan.upload", locale),
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
                            t("plan.execute", locale),
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
