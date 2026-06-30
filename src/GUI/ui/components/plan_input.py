import gradio as gr
from pathlib import Path
from functions.utils.file_loader.main import main as run_file_loader_action
from functions.utils.path_utils import find_project_root

def build_plan_input() -> tuple[
    gr.Tab, gr.Tab, gr.Tab, gr.Column, gr.Column, list[gr.Textbox], gr.Button, gr.Button, gr.Button, gr.Button,
    list[gr.Textbox], gr.Button, gr.Button, gr.Button
]:
    """
    构建同级的“计划输入”、“计划输出”和“计划修改” Tab 组件，初始均不可见。
    """
    with gr.Tab("计划输入", id="file_processing_tab", visible=False) as plan_input_tab:
        with gr.Column(elem_id="plan-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="plan-input-panel"):
                # 头部带有关闭按钮的行
                with gr.Row(variant="compact", elem_id="plan-input-header"):
                    with gr.Column(scale=4):
                        gr.Markdown(
                            """
                            ### 🧭 计划输入区 (Plan Input)
                            填写以下 LCA 项目的需求细节，填写完成后点击下方 **⚡ 执行计划** 启动任务。
                            """
                        )
                    with gr.Column(scale=1, min_width=150):
                        close_btn = gr.Button("❌ 关闭计划", variant="secondary", size="sm", elem_id="close-plan-btn")

                # 左右布局：左侧是目录导航，右侧是滚动输入表单
                with gr.Row(elem_id="plan-input-content-row"):
                    project_root = find_project_root(Path(__file__))
                    plan_path = project_root / "src" / "GUI" / "ui" / "assets" / "template" / "plan.md"

                    with gr.Column(scale=1, min_width=220, elem_id="plan-toc-column"):
                        gr.HTML(run_file_loader_action("extract_toc", filepath=plan_path))

                    with gr.Column(scale=3, elem_id="plan-template-column"):
                        with gr.Column(elem_id="plan-template-container") as plan_template_container:
                            # 滚动容器只负责高度与滚动；内层保持普通文档流，避免影响 Markdown 渲染。
                            with gr.Column(elem_id="plan-template-content"):
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
                with gr.Row(elem_id="template-actions-row"):
                    clear_fields_btn = gr.Button("🧹 清空输入", variant="secondary")
                    load_plan_btn = gr.UploadButton("📂 加载计划", file_types=[".md"], variant="secondary")
                    exec_plan_btn = gr.Button("⚡ 执行计划", variant="primary")

    with gr.Tab("计划输出", id="plan_output_tab", visible=False) as plan_output_tab:
        with gr.Column(elem_id="plan-output-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="plan-output-panel") as plan_output_panel:
                gr.Markdown("### 📤 计划输出区 (Plan Output)")
                gr.Markdown("", elem_id="plan-output-placeholder")

    with gr.Tab("计划修改", id="plan_modification_tab", visible=False) as plan_modification_tab:
        with gr.Column(elem_id="plan-modify-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="plan-modify-panel"):
                # 头部带有关闭按钮的行
                with gr.Row(variant="compact", elem_id="plan-modify-header"):
                    with gr.Column(scale=4):
                        gr.Markdown(
                            """
                            ### 🔧 计划修改区 (Plan Modification)
                            如果您对当前的 LCA 执行计划有任何修改意见或有新加入的问题，请在下方填写，完成后点击 **⚡ 执行修改**。
                            """
                        )
                    with gr.Column(scale=1, min_width=150):
                        close_modify_btn = gr.Button("❌ 关闭计划", variant="secondary", size="sm", elem_id="close-modify-btn")

                # 左右布局：左侧是目录导航，右侧是滚动输入表单
                with gr.Row(elem_id="plan-modify-content-row"):
                    project_root = find_project_root(Path(__file__))
                    modify_template_path = project_root / "src" / "GUI" / "ui" / "assets" / "template" / "modify_plan.md"

                    with gr.Column(scale=1, min_width=220, elem_id="plan-modify-toc-column"):
                        gr.HTML(run_file_loader_action("extract_toc", filepath=modify_template_path))

                    with gr.Column(scale=3, elem_id="plan-modify-template-column"):
                        with gr.Column(elem_id="plan-modify-template-container") as plan_modify_template_container:
                            with gr.Column(elem_id="plan-modify-template-content"):
                                modify_blocks = run_file_loader_action("parse_template", filepath=modify_template_path)

                                modify_textbox_components = []

                                for block in modify_blocks:
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
                                        modify_textbox_components.append(tb)

                # 控制按钮，固定放置在底部
                with gr.Row(elem_id="modify-actions-row"):
                    clear_modify_btn = gr.Button("🧹 清空输入", variant="secondary")
                    exec_modify_btn = gr.Button("⚡ 执行修改", variant="primary")
            
    return (
        plan_input_tab, plan_output_tab, plan_modification_tab,
        plan_template_container, plan_output_panel,
        textbox_components, clear_fields_btn, load_plan_btn, exec_plan_btn, close_btn,
        modify_textbox_components, clear_modify_btn, exec_modify_btn, close_modify_btn
    )
