import gradio as gr

from ui.components.render_mdfile import (
    MarkdownDocumentView,
    build_markdown_document_view,
)


def build_tab_result() -> tuple[
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
    import config

    report_relative_path = config.LCA_REPORT_RELATIVE_PATH.as_posix()
    with gr.Tab(
        "LCA评估结果",
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
                    document_label="LCA 报告",
                    template_label="LCA 报告",
                    heading_levels=(1, 2, 3),
                    toc_title="LCA 结果目录",
                    status_heading="### 📊 LCA 结果报告",
                    show_load_status=False,
                )
                report_warning = gr.Markdown(
                    (
                        "### ⚠️ 缺少 LCA 报告\n\n"
                        f"未找到 `{report_relative_path}`。"
                    ),
                    visible=False,
                )
                with gr.Row(elem_classes=["panel-actions-row"]):
                    download_report_btn = gr.DownloadButton(
                        "下载LCA报告",
                        variant="secondary",
                        interactive=False,
                        elem_id="download-lca-report-btn",
                    )
                    show_lci_btn = gr.Button(
                        "显示LCI清单",
                        variant="secondary",
                        elem_id="show-lci-list-btn",
                    )
                    modify_rerun_btn = gr.Button(
                        "修改LCA评估",
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
