import gradio as gr

def build_project_init() -> tuple[gr.Tab, gr.Button, gr.Button]:
    """
    构建右侧“项目初始化” Tab 组件，初始不可见。
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
                            点击下方 **⚡ 执行项目初始化** 按钮启动任务，清空旧数据并根据上传文件重构数据库。
                            """
                        )
                    with gr.Column(scale=1, min_width=150):
                        close_init_btn = gr.Button("❌ 关闭初始化面板", variant="secondary", size="sm", elem_id="close-init-btn", elem_classes=["panel-close-btn"])

                # 内容区：说明文件要求与项目初始化执行流程
                with gr.Row(elem_id="project-init-content-row", elem_classes=["panel-content-row"]):
                    with gr.Column(scale=1, elem_id="project-init-template-column", elem_classes=["panel-template-column"]):
                        with gr.Column(elem_id="project-init-template-container", elem_classes=["panel-scroll-container"]):
                            with gr.Column(elem_id="project-init-template-content", elem_classes=["panel-scroll-content"]):
                                gr.Markdown(
                                    """
                                    #### 📋 初始化说明与操作指引
                                    
                                    在启动项目初始化之前，请确认以下内容：
                                    
                                    1. **参考资料上传**：在左侧文件交换区切换至 **参考资料** 标签页，并上传所需参考文档（支持 PDF/Markdown 等格式）。
                                    2. **参考数据上传**：在左侧文件交换区切换至 **参考数据** 标签页，上传所需的参考 Excel 或其他结构化数据。
                                    3. **旧数据清理**：执行初始化后，系统将会自动清空 `src/input/user_file` 与 `src/input/user_data` 下的旧文件，请注意备份。
                                    
                                    ---
                                    
                                    #### ⚙️ 初始化执行步骤
                                    
                                    点击底部的 **⚡ 执行项目初始化** 后，系统将按顺序执行：
                                    
                                    - **Step 1/3**: 清理工作空间中的历史多余数据。
                                    - **Step 2/3**: 将您在左侧文件交换区上传的最新文件拷贝至工作目录。
                                    - **Step 3/3**: 启动后端 RAG 索引与 LCA 相关辅助环境初始化。
                                    """
                                )

                # 控制按钮，固定放置在底部
                with gr.Row(elem_id="project-init-actions-row", elem_classes=["panel-actions-row"]):
                    exec_init_btn = gr.Button("⚡ 执行项目初始化", variant="primary")

    return project_init_tab, close_init_btn, exec_init_btn
