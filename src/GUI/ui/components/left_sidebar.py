import gradio as gr


def build_left_sidebar() -> tuple[
    gr.Button,
    gr.Button,
    gr.File,
]:
    """
    构建左侧栏：文件交换区与快捷操作区。
    """
    with gr.Group(elem_id="file-exchange-section"):
        gr.Markdown(
            """
            ### 📁 文件交换区
            上传用于智能体制定LCA报告的参考资料
            """
        )
        ref_upload_file = gr.File(
            label="用户资料上传 (User Materials)",
            file_count="multiple",
            interactive=True,
            elem_id="reference-upload",
        )

    with gr.Column(elem_id="quick-actions-section"):
        gr.Markdown(
            """
            ### 🛠️ 快捷操作区 (Quick Actions)
            本面板用于触发 LCA 系统运行的预设任务。
            """
        )

        open_init_btn = gr.Button(
            "设置&初始化",
            variant="secondary",
            size="lg",
            interactive=True,
            elem_id="quick-action-project",
            elem_classes=["quick-action-btn"],
        )
        start_lca_btn = gr.Button(
            "开始LCA工作",
            variant="secondary",
            size="lg",
            interactive=True,
            elem_id="quick-action-start-lca",
            elem_classes=["quick-action-btn"],
        )

    return (
        open_init_btn,
        start_lca_btn,
        ref_upload_file,
    )
