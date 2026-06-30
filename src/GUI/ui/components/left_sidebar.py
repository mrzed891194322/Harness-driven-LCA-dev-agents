import gradio as gr


def build_left_sidebar() -> tuple[gr.Button, gr.Button, gr.Button, gr.File, gr.File]:
    """
    构建左侧栏：文件交换区与快捷操作区。
    """
    with gr.Group(elem_id="file-exchange-section"):
        gr.Markdown(
            """
            ### 📁 文件交换区
            点击标签切换参考资料与参考数据上传视图。
            """
        )
        with gr.Tabs():
            with gr.Tab("参考资料"):
                ref_materials_file = gr.File(
                    label="参考资料上传 (Reference Materials)",
                    file_count="multiple",
                    interactive=True,
                    elem_id="reference-materials-upload",
                )
            with gr.Tab("参考数据"):
                ref_data_file = gr.File(
                    label="参考数据上传 (Reference Data)",
                    file_count="multiple",
                    interactive=True,
                    elem_id="reference-data-upload",
                )

    with gr.Column(elem_id="quick-actions-section"):
        gr.Markdown(
            """
            ### 🛠️ 快捷操作区 (Quick Actions)
            本面板用于触发 LCA 系统运行的预设任务。
            """
        )

        run_btn = gr.Button("🚀 项目初始化 (Project Init)", variant="primary", size="lg")
        make_plan_btn = gr.Button("🧭 制定 LCA 执行计划 (Make Plan)", variant="secondary", size="lg")
        design_lci_btn = gr.Button("🧬 设计 LCI 数据 (Design LCI)", variant="secondary", size="lg")

    return run_btn, make_plan_btn, design_lci_btn, ref_materials_file, ref_data_file
