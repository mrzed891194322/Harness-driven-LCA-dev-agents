import gradio as gr

from ui.components.render_mdfile import (
    MarkdownDocumentView,
    build_markdown_document_view,
)


def build_tab_lci() -> tuple[
    gr.Tab,
    gr.Button,
    MarkdownDocumentView,
    gr.Row,
    gr.DownloadButton,
    gr.Button,
]:
    """Build the mounted, on-demand LCI inventory Markdown tab."""
    import config

    mapping_relative_path = config.LCI_MAPPING_RELATIVE_PATH.as_posix()
    with gr.Tab("LCI清单", id="lci_mapping_tab") as lci_mapping_tab:
        with gr.Column(
            elem_id="lci-mapping-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            with gr.Column(
                elem_id="lci-mapping-panel",
                elem_classes=["inner-panel-grid"],
            ):
                lci_mapping_view = build_markdown_document_view(
                    component_prefix="lci-mapping",
                    document_label="LCI 清单",
                    template_label="LCI 清单",
                    heading_levels=(1, 2, 3),
                    toc_title="清单目录导航",
                    status_heading=(
                        "### 🗺️ LCI 清单 (Human-readable Mapping)\n\n"
                        f"这里渲染 `{mapping_relative_path}`，用于人工检查 "
                        "LCI 数据构建逻辑、来源追溯与过程拓扑。"
                    ),
                    show_load_status=False,
                    content_visible=False,
                )

                with gr.Row(
                    elem_id="lci-mapping-warning-row",
                    visible=True,
                ) as lci_mapping_warning_row:
                    gr.Markdown(
                        "### ⚠️ 缺少必要文件",
                        elem_id="missing-lci-mapping-file-warning",
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
                    download_lci_mapping_btn = gr.DownloadButton(
                        "📥 下载LCI清单",
                        variant="secondary",
                        interactive=False,
                    )
                    modify_lci_btn = gr.Button(
                        "修改LCI清单",
                        variant="primary",
                        interactive=False,
                        elem_id="modify-lci-inventory-btn",
                    )

    return (
        lci_mapping_tab,
        close_mapping_btn,
        lci_mapping_view,
        lci_mapping_warning_row,
        download_lci_mapping_btn,
        modify_lci_btn,
    )
