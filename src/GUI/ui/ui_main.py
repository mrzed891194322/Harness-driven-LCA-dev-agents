from pathlib import Path
import gradio as gr
from utils.executor import (
    run_design_lci_console,
    run_init_rag_database_console,
    run_make_plan_console,
)
from utils.plan_loader import (
    load_user_values,
    save_user_values,
)
from ui.components.terminal_console import build_terminal_console
from ui.components.plan_input import build_plan_input
from ui.components.left_sidebar import build_left_sidebar

def build_ui() -> tuple[gr.Blocks, gr.themes.Soft, str]:
    theme = gr.themes.Soft(
        primary_hue="teal",
        secondary_hue="indigo",
        neutral_hue="slate"
    )
    
    assets_dir = Path(__file__).resolve().parent / "assets"
    css_file = assets_dir / "css" / "style.css"
    css = css_file.read_text(encoding="utf-8") if css_file.exists() else ""

    with gr.Blocks(title="LCA Multi-agent UI") as demo:
        with gr.Row():
            gr.Markdown(
                """
                # 🌲 生命周期评估多智能体系统 - 控制面板
                ---
                """
            )
            
        with gr.Row(elem_id="main-layout-row"):
            with gr.Column(scale=1, elem_id="left-sidebar"):
                run_btn, make_plan_btn, design_lci_btn = build_left_sidebar()
                
            with gr.Column(scale=2, elem_id="right-panel"):
                with gr.Tabs(elem_id="right-tabs") as right_tabs:
                    # 1. 拆分出的“终端显示”组件
                    _, output_console, status, clear_btn = build_terminal_console()
                    
                    # 2. 拆分出的“计划输入”（改名自“文件处理”，初始不可见）
                    (
                        plan_input_tab,
                        plan_template_container,
                        textbox_components,
                        clear_fields_btn,
                        load_plan_btn,
                        exec_plan_btn,
                        close_btn
                    ) = build_plan_input()
                
        # 绑定事件
        run_btn.click(
            fn=run_init_rag_database_console,
            inputs=None,
            outputs=[output_console, status]
        )

        # 点击左侧“制定 LCA 执行计划”按钮：显示并切换到“计划输入” Tab
        make_plan_btn.click(
            fn=lambda: (gr.Tabs(selected="file_processing_tab"), gr.Tab(visible=True)),
            inputs=None,
            outputs=[right_tabs, plan_input_tab]
        )

        # 点击右侧“❌ 关闭计划输入”按钮：隐藏“计划输入” Tab 并返回到“终端显示” Tab
        close_btn.click(
            fn=lambda: (gr.Tabs(selected="terminal_tab"), gr.Tab(visible=False)),
            inputs=None,
            outputs=[right_tabs, plan_input_tab]
        )

        # 绑定“计划输入”下方的控制按钮逻辑
        clear_fields_btn.click(
            fn=lambda: [""] * len(textbox_components),
            inputs=None,
            outputs=textbox_components
        )

        def read_user_plan_values(file_obj):
            if file_obj is None:
                raise gr.Error("未选择任何文件！")
            
            uploaded_filepath = Path(file_obj.name)
            vals = load_user_values(uploaded_filepath)
            
            # 校验是否可以使用现有渲染逻辑（检查解析出的用户填写区域块数是否与当前模板相符）
            if len(vals) != len(textbox_components):
                raise gr.Error(
                    f"文件格式不兼容！所选文件包含 {len(vals)} 个填写区，"
                    f"而当前界面配置需要 {len(textbox_components)} 个填写区。无法使用现有逻辑进行渲染。"
                )
            return vals

        load_plan_btn.upload(
            fn=read_user_plan_values,
            inputs=load_plan_btn,
            outputs=textbox_components
        )

        def run_exec_plan_flow(*args):
            values = list(args)
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            template_path = project_root / "src" / "GUI" / "ui" / "assets" / "template" / "plan.md"
            target_path = project_root / "input" / "plan.md"
            
            # 保存当前界面的文本框输入到目标 input/plan.md
            save_user_values(template_path, target_path, values)
            
            # 切换回终端显示 Tab，并隐藏计划输入 Tab
            yield (
                gr.Tabs(selected="terminal_tab"),
                gr.Tab(visible=False),
                "[System] 已更新保存 input/plan.md。正在启动后台制定 LCA 计划任务...\n",
                "Running"
            )
            
            # 运行后台命令并以流式输出至终端显示
            for chunk in run_make_plan_console():
                yield gr.Tabs(selected="terminal_tab"), gr.Tab(visible=False), chunk[0], chunk[1]

        exec_plan_btn.click(
            fn=run_exec_plan_flow,
            inputs=textbox_components,
            outputs=[right_tabs, plan_input_tab, output_console, status]
        )

        design_lci_btn.click(
            fn=run_design_lci_console,
            inputs=None,
            outputs=[output_console, status]
        )
        
        clear_btn.click(
            fn=lambda: ("", "Ready"),
            inputs=None,
            outputs=[output_console, status]
        )
        
    return demo, theme, css
