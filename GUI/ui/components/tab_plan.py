import gradio as gr
from pathlib import Path
from functions.utils.file_loader.main import main as run_file_loader_action
from functions.utils.path_utils import find_project_root

def build_tab_plan() -> tuple:
    """
    构建同级的“计划输入”、“计划输出”和“计划修改” Tab 组件，初始均不可见。
    """
    with gr.Tab("计划输入", id="file_processing_tab") as plan_input_tab:
        with gr.Column(elem_id="plan-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="plan-input-panel", elem_classes=["inner-panel-grid"]):
                # 头部带有关闭按钮的行
                with gr.Row(variant="compact", elem_id="plan-input-header", elem_classes=["panel-header-row"]):
                    with gr.Column(scale=4):
                        gr.Markdown(
                            """
                            ### 🧭 计划输入区 (Plan Input)
                            填写以下 LCA 项目的需求细节，填写完成后点击下方 **⚡ 执行计划** 启动任务。
                            """
                        )
                    with gr.Column(scale=1, min_width=150):
                        close_btn = gr.Button("❌ 关闭计划制定面板", variant="secondary", size="sm", elem_id="close-plan-btn", elem_classes=["panel-close-btn"])

                # 左右布局：左侧是目录导航，右侧是滚动输入表单
                with gr.Row(elem_id="plan-input-content-row", elem_classes=["panel-content-row"]):
                    import config
                    plan_path = config.PLAN_INPUT_TEMPLATE_PATH

                    with gr.Column(scale=1, min_width=220, elem_id="plan-toc-column"):
                        gr.HTML(run_file_loader_action("extract_toc", filepath=plan_path))

                    with gr.Column(scale=3, elem_id="plan-template-column", elem_classes=["panel-template-column"]):
                        with gr.Column(elem_id="plan-template-container", elem_classes=["panel-scroll-container"]) as plan_template_container:
                            # 滚动容器只负责高度与滚动；内层保持普通文档流，避免影响 Markdown 渲染。
                            with gr.Column(elem_id="plan-template-content", elem_classes=["panel-scroll-content"]):
                                blocks = run_file_loader_action("parse_template", filepath=plan_path)

                                textbox_components = []

                                # 循环创建所有静态 Markdown 与交互式 Textbox
                                for block in blocks:
                                    if block["type"] == "markdown":
                                        gr.Markdown(block["content"])
                                    elif block["type"] == "textbox":
                                        tb = gr.Textbox(
                                            label=block["label"],
                                            placeholder=block["placeholder"],
                                            value="",
                                            lines=3,
                                            interactive=True
                                        )
                                        textbox_components.append(tb)

                # 三个控制按钮，固定放置在滚动容器外部（底部）
                with gr.Row(elem_id="template-actions-row", elem_classes=["panel-actions-row"]):
                    clear_fields_btn = gr.Button("🧹 清空输入", variant="secondary")
                    load_plan_btn = gr.UploadButton("📂 加载计划", file_types=[".md"], variant="secondary")
                    exec_plan_btn = gr.Button("⚡ 执行计划", variant="primary")

    with gr.Tab("计划输出", id="plan_output_tab") as plan_output_tab:
        with gr.Column(elem_id="plan-output-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="plan-output-panel", elem_classes=["inner-panel-grid"]) as plan_output_panel:
                # 头部带有关闭按钮的行
                with gr.Row(variant="compact", elem_id="plan-output-header", elem_classes=["panel-header-row"]):
                    with gr.Column(scale=4):
                        gr.Markdown(
                            """
                            ### 📤 计划输出区 (Plan Output)
                            这是已生成的生命周期评估 (LCA) 执行计划。请在此进行查看、下载或确认。
                            """
                        )
                    with gr.Column(scale=1, min_width=150):
                        close_output_btn = gr.Button("❌ 关闭计划制定面板", variant="secondary", size="sm", elem_id="close-output-btn", elem_classes=["panel-close-btn"])

                # 左右布局：左侧是目录导航，右侧是滚动展示
                with gr.Row(elem_id="plan-output-content-row", elem_classes=["panel-content-row"], visible=False) as plan_output_content_row:
                    with gr.Column(scale=1, min_width=220, elem_id="plan-output-toc-column") as plan_output_toc_column:
                        plan_output_toc_html = gr.HTML()

                    with gr.Column(scale=3, elem_id="plan-output-template-column", elem_classes=["panel-template-column"]):
                        with gr.Column(elem_id="plan-output-template-container", elem_classes=["panel-scroll-container"]) as plan_output_template_container:
                            with gr.Column(elem_id="plan-output-template-content", elem_classes=["panel-scroll-content"]):
                                plan_output_markdown = gr.Markdown()

                with gr.Row(elem_id="plan-output-warning-row", visible=True) as plan_output_warning_row:
                    gr.Markdown("### ⚠️ 缺少必要文件", elem_id="missing-output-file-warning")

                # 控制按钮，固定放置在底部
                with gr.Row(elem_id="output-actions-row", elem_classes=["panel-actions-row"]):
                    download_plan_btn = gr.DownloadButton("📥 下载计划", variant="secondary", interactive=False)
                    modify_plan_btn = gr.Button("🔧 修改计划", variant="secondary", interactive=False)
                    confirm_plan_btn = gr.Button("✅ 确认计划", variant="primary", interactive=False)

    with gr.Tab("计划修改", id="plan_modification_tab") as plan_modification_tab:
        with gr.Column(elem_id="plan-modify-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="plan-modify-panel", elem_classes=["inner-panel-grid"]):
                # 头部带有关闭按钮的行
                with gr.Row(variant="compact", elem_id="plan-modify-header", elem_classes=["panel-header-row"]):
                    with gr.Column(scale=4):
                        gr.Markdown(
                            """
                            ### 🔧 计划修改区 (Plan Modification)
                            如果您对当前的 LCA 执行计划有任何修改意见或有新加入的问题，请在下方填写，完成后点击 **⚡ 执行修改**。
                            """
                        )
                    with gr.Column(scale=1, min_width=150):
                        close_modify_btn = gr.Button("❌ 关闭计划制定面板", variant="secondary", size="sm", elem_id="close-modify-btn", elem_classes=["panel-close-btn"])

                # 左右布局：左侧是目录导航，右侧是滚动输入表单
                with gr.Row(elem_id="plan-modify-content-row", elem_classes=["panel-content-row"], visible=False) as plan_modify_content_row:
                    with gr.Column(scale=1, min_width=220, elem_id="plan-modify-toc-column") as plan_modify_toc_column:
                        plan_modify_toc_html = gr.HTML()

                    with gr.Column(scale=3, elem_id="plan-modify-template-column", elem_classes=["panel-template-column"]):
                        with gr.Column(elem_id="plan-modify-template-container", elem_classes=["panel-scroll-container"]) as plan_modify_template_container:
                            with gr.Column(elem_id="plan-modify-template-content", elem_classes=["panel-scroll-content"]):
                                modify_markdown_pool = []
                                modify_textbox_pool = []
                                for i in range(20):
                                    md_item = gr.Markdown(visible=False)
                                    tb_item = gr.Textbox(visible=False, interactive=True, lines=3)
                                    modify_markdown_pool.append(md_item)
                                    modify_textbox_pool.append(tb_item)

                with gr.Row(elem_id="plan-modify-warning-row", visible=True) as plan_modify_warning_row:
                    gr.Markdown("### ⚠️ 缺少必要文件", elem_id="missing-file-warning")

                # 控制按钮，固定放置在底部
                with gr.Row(elem_id="modify-actions-row", elem_classes=["panel-actions-row"]):
                    clear_modify_btn = gr.Button("🧹 清空输入", variant="secondary", interactive=False)
                    exec_modify_btn = gr.Button("⚡ 执行修改", variant="primary", interactive=False)
            
    return (
        plan_input_tab, plan_output_tab, plan_modification_tab,
        plan_template_container, plan_output_panel,
        textbox_components, clear_fields_btn, load_plan_btn, exec_plan_btn, close_btn,
        modify_textbox_pool, clear_modify_btn, exec_modify_btn, close_modify_btn,
        download_plan_btn, modify_plan_btn, confirm_plan_btn, close_output_btn,
        plan_output_content_row, plan_output_warning_row, plan_output_toc_html, plan_output_markdown,
        plan_modify_content_row, plan_modify_warning_row, plan_modify_toc_html, modify_markdown_pool
    )
