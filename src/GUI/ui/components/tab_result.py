import gradio as gr


def build_tab_result() -> tuple:
    import config

    report_relative_path = config.LCA_REPORT_RELATIVE_PATH.as_posix()
    with gr.Tab("LCA执行结果", id="lca_result_tab") as result_tab:
        with gr.Column(
            elem_id="lca-result-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            result_heading = gr.Markdown(visible=False)
            with gr.Column(visible=False) as success_panel:
                report_markdown = gr.Markdown()
                report_warning = gr.Markdown(
                    f"### ⚠️ 缺少 LCA 报告\n\n未找到 `{report_relative_path}`。",
                    visible=False,
                )
                with gr.Row():
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
        report_markdown,
        report_warning,
        download_report_btn,
        show_lci_btn,
        modify_rerun_btn,
    )
