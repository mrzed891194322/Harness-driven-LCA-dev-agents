import gradio as gr


def build_tab_lci() -> tuple:
    """
    构建按需显示的只读“LCI 映射”Tab。
    """
    import config

    mapping_relative_path = config.LCI_MAPPING_RELATIVE_PATH.as_posix()
    with gr.Tab(
        "LCI映射",
        id="lci_mapping_tab",
        visible=False,
    ) as lci_mapping_tab:
        with gr.Column(elem_id="lci-mapping-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="lci-mapping-panel", elem_classes=["inner-panel-grid"]):
                with gr.Row(variant="compact", elem_id="lci-mapping-header", elem_classes=["panel-header-row"]):
                    with gr.Column(scale=4):
                        gr.Markdown(
                            f"""
                            ### 🗺️ LCI 映射报告 (Human-readable Mapping)
                            这里渲染 `{mapping_relative_path}`，用于人工检查 LCI 数据构建逻辑、来源追溯与过程拓扑。
                            """
                        )
                    with gr.Column(scale=1, min_width=150):
                        close_mapping_btn = gr.Button(
                            "❌ 关闭 LCI 面板",
                            variant="secondary",
                            size="sm",
                            interactive=False,
                            elem_id="close-lci-mapping-btn",
                            elem_classes=["panel-close-btn"],
                        )

                with gr.Row(elem_id="lci-mapping-content-row", elem_classes=["panel-content-row"], visible=False) as lci_mapping_content_row:
                    with gr.Column(scale=1, min_width=220, elem_id="lci-mapping-toc-column"):
                        lci_mapping_toc_html = gr.HTML()

                    with gr.Column(scale=3, elem_id="lci-mapping-template-column", elem_classes=["panel-template-column"]):
                        with gr.Column(elem_id="lci-mapping-template-container", elem_classes=["panel-scroll-container"]):
                            with gr.Column(elem_id="lci-mapping-template-content", elem_classes=["panel-scroll-content"]):
                                lci_mapping_markdown = gr.Markdown()

                with gr.Row(elem_id="lci-mapping-warning-row", visible=True) as lci_mapping_warning_row:
                    gr.Markdown("### ⚠️ 缺少必要文件", elem_id="missing-lci-mapping-file-warning")

                with gr.Row(elem_id="lci-mapping-actions-row", elem_classes=["panel-actions-row"]):
                    download_lci_mapping_btn = gr.DownloadButton("📥 下载映射报告", variant="secondary", interactive=False)
                    modify_lci_btn = gr.Button(
                        "修改LCI清单",
                        variant="primary",
                        interactive=False,
                        elem_id="modify-lci-inventory-btn",
                    )

    return (
        lci_mapping_tab,
        close_mapping_btn,
        lci_mapping_content_row,
        lci_mapping_warning_row,
        lci_mapping_toc_html,
        lci_mapping_markdown,
        download_lci_mapping_btn,
        modify_lci_btn,
    )
