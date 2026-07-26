import gradio as gr


def build_left_sidebar() -> tuple[
    gr.Button,
    gr.Button,
    gr.Button,
    gr.File,
    gr.File,
]:
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

        open_init_btn = gr.Button(
            "打开初始化面板",
            variant="secondary",
            size="lg",
            interactive=True,
            elem_id="quick-action-project",
            elem_classes=["quick-action-btn"],
        )
        start_lca_btn = gr.Button(
            "开始LCA工作",
            variant="primary",
            size="lg",
            interactive=True,
            elem_id="quick-action-start-lca",
            elem_classes=["quick-action-btn"],
        )
        view_lca_result_btn = gr.Button(
            "查看LCA结果(仅开发过程使用)",
            variant="secondary",
            size="lg",
            elem_id="quick-action-view-results",
            elem_classes=["quick-action-btn"],
        )

    return (
        open_init_btn,
        start_lca_btn,
        view_lca_result_btn,
        ref_materials_file,
        ref_data_file,
    )
