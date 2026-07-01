import gradio as gr


def _build_status_card(title: str, description: str, action_label: str, accent_class: str) -> tuple[gr.Markdown, gr.Button]:
    """
    构建单张状态检测卡片。

    Returns:
        (status_value, action_btn) — status_value 用于后续更新检测状态文本，
        action_btn 用于绑定卡片内的操作按钮。
    """
    with gr.Column(elem_classes=["project-init-status-card", accent_class]):
        gr.Markdown(f"### {title}", elem_classes=["project-init-status-title"])
        gr.Markdown(description, elem_classes=["project-init-status-description"])
        with gr.Column(elem_classes=["project-init-status-value-container"]):
            status_value = gr.Markdown("未检测", elem_classes=["project-init-status-value"])
        action_btn = gr.Button(action_label, variant="secondary", size="sm", elem_classes=["project-init-card-action"])
    return status_value, action_btn


def build_project_init() -> tuple:
    """
    构建右侧"项目初始化" Tab 组件，初始不可见。

    Returns:
        (project_init_tab, close_init_btn, refresh_init_status_btn, exec_init_btn,
         clean_status, rag_status, openlca_status, openlca_recheck_btn)
    """
    with gr.Tab("项目初始化", id="project_init_tab") as project_init_tab:
        with gr.Column(elem_id="project-init-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="project-init-panel", elem_classes=["inner-panel-grid"]):
                # 头部带有关闭按钮的行
                with gr.Row(variant="compact", elem_id="project-init-header", elem_classes=["panel-header-row"]):
                    with gr.Column(scale=4):
                        gr.Markdown(
                            """
                            ### 🚀 项目初始化 (Project Initialization)
                            """
                        )
                    with gr.Column(scale=1, min_width=150):
                        close_init_btn = gr.Button("❌ 关闭初始化面板", variant="secondary", size="sm", elem_id="close-init-btn", elem_classes=["panel-close-btn"])

                # 内容区：项目初始化前置状态概览
                with gr.Row(elem_id="project-init-content-row", elem_classes=["panel-content-row"]):
                    with gr.Column(scale=1, elem_id="project-init-template-column", elem_classes=["panel-template-column"]):
                        with gr.Row(elem_id="project-init-status-row"):
                            clean_status, clean_btn = _build_status_card("目录清理", "工作目录与历史缓存状态", "执行清理", "status-card-clean")
                            rag_status, rag_btn = _build_status_card("RAG知识库", "参考资料索引与向量库状态", "构建知识库", "status-card-rag")
                            openlca_status, openlca_recheck_btn = _build_status_card("openLCA状态", "openLCA 连接与服务状态", "重新检查", "status-card-openlca")

                # 控制按钮，固定放置在底部
                with gr.Row(elem_id="project-init-actions-row", elem_classes=["panel-actions-row"]):
                    refresh_init_status_btn = gr.Button("刷新检测状态", variant="secondary")
                    exec_init_btn = gr.Button("⚡ 执行项目初始化", variant="primary")

    return (
        project_init_tab,
        close_init_btn,
        refresh_init_status_btn,
        exec_init_btn,
        clean_status,
        clean_btn,
        rag_status,
        rag_btn,
        openlca_status,
        openlca_recheck_btn,
    )
