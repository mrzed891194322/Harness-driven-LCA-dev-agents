import gradio as gr


def build_tab_lci() -> tuple[
    gr.Tab,
    gr.Button,
    gr.JSON,
    gr.Markdown,
    gr.DownloadButton,
    gr.JSON,
    gr.Markdown,
    gr.DownloadButton,
    gr.Button,
]:
    """Build the mounted work-details tab with two stacked JSON trees."""
    import config

    bom_relative = config.EXTRACTED_BOM_RELATIVE_PATH.as_posix()
    mapping_relative = config.PROCESS_MAPPING_RELATIVE_PATH.as_posix()
    with gr.Tab("工作细节", id="lci_mapping_tab") as lci_mapping_tab:
        with gr.Column(
            elem_id="lci-mapping-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            with gr.Column(
                elem_id="lci-mapping-panel",
                elem_classes=["inner-panel-grid"],
            ):
                gr.Markdown("### 工作细节")
                with gr.Column(
                    elem_id="work-details-scroll",
                    elem_classes=["panel-scroll-container"],
                ):
                    gr.Markdown(
                        f"#### 物料清单\n\n`{bom_relative}`",
                        elem_id="work-details-bom-heading",
                    )
                    bom_json = gr.JSON(
                        value=None,
                        show_label=False,
                        open=True,
                        visible=False,
                        max_height=400,
                        elem_id="work-details-bom-json",
                    )
                    bom_warning = gr.Markdown(
                        (
                            "### ⚠️ 缺少物料清单\n\n"
                            f"未找到有效的 `{bom_relative}`。"
                        ),
                        visible=True,
                        elem_id="work-details-bom-warning",
                    )

                    gr.Markdown(
                        f"#### 工艺映射\n\n`{mapping_relative}`",
                        elem_id="work-details-mapping-heading",
                    )
                    mapping_json = gr.JSON(
                        value=None,
                        show_label=False,
                        open=True,
                        visible=False,
                        max_height=400,
                        elem_id="work-details-mapping-json",
                    )
                    mapping_warning = gr.Markdown(
                        (
                            "### ⚠️ 缺少工艺映射\n\n"
                            f"未找到有效的 `{mapping_relative}`。"
                        ),
                        visible=True,
                        elem_id="work-details-mapping-warning",
                    )

                with gr.Row(
                    elem_id="lci-mapping-actions-row",
                    elem_classes=["panel-actions-row"],
                ):
                    close_mapping_btn = gr.Button(
                        "关闭面板",
                        variant="secondary",
                        elem_id="close-lci-mapping-btn",
                    )
                    download_bom_btn = gr.DownloadButton(
                        "下载物料清单",
                        variant="secondary",
                        interactive=False,
                        elem_id="download-extracted-bom-btn",
                    )
                    download_mapping_btn = gr.DownloadButton(
                        "下载工艺映射",
                        variant="secondary",
                        interactive=False,
                        elem_id="download-process-mapping-btn",
                    )
                    modify_lci_btn = gr.Button(
                        "修改工作细节",
                        variant="primary",
                        interactive=False,
                        elem_id="modify-lci-inventory-btn",
                    )

    return (
        lci_mapping_tab,
        close_mapping_btn,
        bom_json,
        bom_warning,
        download_bom_btn,
        mapping_json,
        mapping_warning,
        download_mapping_btn,
        modify_lci_btn,
    )
