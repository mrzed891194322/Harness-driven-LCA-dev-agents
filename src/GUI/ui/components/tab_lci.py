import gradio as gr


def build_tab_lci() -> tuple[gr.Tab, gr.Button, gr.Button]:
    """
    构建右侧“LCI 制定” Tab 组件。
    """
    with gr.Tab("LCI制定", id="lci_design_tab") as lci_design_tab:
        with gr.Column(elem_id="lci-design-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="lci-design-panel", elem_classes=["inner-panel-grid"]):
                with gr.Row(variant="compact", elem_id="lci-design-header", elem_classes=["panel-header-row"]):
                    with gr.Column(scale=4):
                        gr.Markdown(
                            """
                            ### 🧬 生命周期清单制定 (LCI Design)
                            点击下方 **⚡ 执行 LCI 制定** 按钮启动生命周期清单相关工作流。
                            """
                        )
                    with gr.Column(scale=1, min_width=150):
                        close_lci_btn = gr.Button(
                            "❌ 关闭 LCI 面板",
                            variant="secondary",
                            size="sm",
                            elem_id="close-lci-btn",
                            elem_classes=["panel-close-btn"],
                        )

                with gr.Row(elem_id="lci-design-content-row", elem_classes=["panel-content-row"]):
                    with gr.Column(scale=1, elem_id="lci-design-template-column", elem_classes=["panel-template-column"]):
                        with gr.Column(elem_id="lci-design-template-container", elem_classes=["panel-scroll-container"]):
                            with gr.Column(elem_id="lci-design-template-content", elem_classes=["panel-scroll-content"]):
                                gr.Markdown(
                                    """
                                    #### 📋 LCI 制定说明
                                    
                                    在启动 LCI 制定之前，请确认项目初始化与计划制定已完成，且所需参考资料、参考数据已经上传或写入工作目录。
                                    
                                    ---
                                    
                                    #### ⚙️ 执行内容
                                    
                                    点击底部的 **⚡ 执行 LCI 制定** 后，系统将调用后端 `design-lci` 任务，并在终端显示区实时输出执行日志。
                                    """
                                )

                with gr.Row(elem_id="lci-design-actions-row", elem_classes=["panel-actions-row"]):
                    exec_lci_btn = gr.Button("⚡ 执行 LCI 制定", variant="primary")

    return lci_design_tab, close_lci_btn, exec_lci_btn
