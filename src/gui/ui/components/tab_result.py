import gradio as gr

from gui.i18n import t
from gui.ui.components.render_mdfile import (
    MarkdownDocumentView,
    build_markdown_document_view,
)


def build_tab_result(
    locale: str,
) -> tuple[
    gr.Tab,
    gr.Markdown,
    gr.Column,
    gr.Column,
    gr.Markdown,
    MarkdownDocumentView,
    gr.Markdown,
    gr.DownloadButton,
    gr.Button,
    gr.Button,
]:
    from gui import config

    report_relative_path = config.LCA_REPORT_RELATIVE_PATH.as_posix()
    with gr.Tab(
        t("tab.result", locale),
        id="lca_result_tab",
    ) as result_tab:
        with gr.Column(
            elem_id="lca-result-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            result_heading = gr.Markdown(visible=False)
            with gr.Column(
                visible=False,
                elem_id="lca-result-success-panel",
                elem_classes=["inner-panel-grid"],
            ) as success_panel:
                report_view = build_markdown_document_view(
                    component_prefix="lca-result",
                    document_label=t("result.report_label", locale),
                    template_label=t("result.report_label", locale),
                    heading_levels=(1, 2, 3),
                    toc_title=t("result.toc_title", locale),
                    status_heading=t("result.status_heading", locale),
                    show_load_status=False,
                    locale=locale,
                )
                report_warning = gr.Markdown(
                    t("result.missing_report", locale, path=report_relative_path),
                    visible=False,
                )
                with gr.Row(elem_classes=["panel-actions-row"]):
                    download_report_btn = gr.DownloadButton(
                        t("result.download", locale),
                        variant="secondary",
                        interactive=False,
                        elem_id="download-lca-report-btn",
                    )
                    show_lci_btn = gr.Button(
                        t("result.show_lci", locale),
                        variant="secondary",
                        elem_id="show-work-details-btn",
                    )
                    modify_rerun_btn = gr.Button(
                        t("result.modify", locale),
                        variant="primary",
                        elem_id="modify-lca-assessment-btn",
                    )
            with gr.Column(visible=False) as failure_panel:
                failure_markdown = gr.Markdown()

    return (
        result_tab,
        result_heading,
        success_panel,
        failure_panel,
        failure_markdown,
        report_view,
        report_warning,
        download_report_btn,
        show_lci_btn,
        modify_rerun_btn,
    )
