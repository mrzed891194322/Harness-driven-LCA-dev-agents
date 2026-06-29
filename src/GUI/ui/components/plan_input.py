import gradio as gr
from pathlib import Path
from utils.plan_loader import parse_plan_template, extract_plan_toc

def build_plan_input() -> tuple[gr.Tab, gr.Column, list[gr.Textbox], gr.Button, gr.Button, gr.Button, gr.Button]:
    """
    构建“计划输入” Tab 组件，初始不可见，且操作按钮固定在底部（不在滚动区内）。
    """
    with gr.Tab("计划输入", id="file_processing_tab", visible=False) as tab:
        with gr.Column(elem_id="plan-input-panel", elem_classes=["right-workspace-panel"]):
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
                    close_btn = gr.Button("❌ 关闭计划输入", variant="secondary", size="sm", elem_id="close-plan-btn")

            # 左右布局：左侧是目录导航，右侧是滚动输入表单
            with gr.Row(elem_id="plan-input-content-row"):
                project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
                plan_path = project_root / "src" / "GUI" / "ui" / "assets" / "template" / "plan.md"

                with gr.Column(scale=1, min_width=220, elem_id="plan-toc-column"):
                    gr.HTML(extract_plan_toc(plan_path))

                with gr.Column(scale=3, elem_id="plan-template-column"):
                    with gr.Column(elem_id="plan-template-container") as plan_template_container:
                        # 滚动容器只负责高度与滚动；内层保持普通文档流，避免影响 Markdown 渲染。
                        with gr.Column(elem_id="plan-template-content"):
                            blocks = parse_plan_template(plan_path)

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

            # 2. 三个控制按钮，固定放置在滚动容器外部（底部）
            with gr.Row(elem_id="template-actions-row"):
                clear_fields_btn = gr.Button("🧹 清空输出", variant="secondary")
                load_plan_btn = gr.UploadButton("📂 加载计划", file_types=[".md"], variant="secondary")
                exec_plan_btn = gr.Button("⚡ 执行计划", variant="primary")
            
    return tab, plan_template_container, textbox_components, clear_fields_btn, load_plan_btn, exec_plan_btn, close_btn
