from pathlib import Path
import gradio as gr
from ui.components.terminal_console import build_terminal_console
from ui.components.plan_input import build_plan_input
from ui.components.left_sidebar import build_left_sidebar
from ui.events import bind_ui_events


def build_ui() -> tuple[gr.Blocks, gr.themes.Soft, str]:
    theme = gr.themes.Soft(
        primary_hue="teal",
        secondary_hue="indigo",
        neutral_hue="slate"
    )
    
    assets_dir = Path(__file__).resolve().parent / "assets"
    css_dir = assets_dir / "css"
    css_files = [
        css_dir / "layout.css",
        css_dir / "terminal.css",
        css_dir / "plan.css",
    ]
    css = "\n\n".join(
        css_file.read_text(encoding="utf-8")
        for css_file in css_files
        if css_file.exists()
    )

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
                (
                    run_btn,
                    make_plan_btn,
                    design_lci_btn,
                    ref_materials_file,
                    ref_data_file
                ) = build_left_sidebar()

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
                (
                    run_btn,
                    make_plan_btn,
                    design_lci_btn,
                    ref_materials_file,
                    ref_data_file
                ) = build_left_sidebar()
                
            with gr.Column(scale=2, elem_id="right-panel"):
                with gr.Tabs(elem_id="right-tabs") as right_tabs:
                    # 1. 拆分出的“终端显示”组件
                    _, output_console, status, clear_btn, stop_btn = build_terminal_console()
                    
                    # 2. 拆分出的“计划输入”、“计划输出”和“计划修改”组件（初始不可见）
                    (
                        plan_input_tab,
                        plan_output_tab,
                        plan_modify_tab,
                        plan_template_container,
                        _plan_output_panel,
                        textbox_components,
                        clear_fields_btn,
                        load_plan_btn,
                        exec_plan_btn,
                        close_btn,
                        modify_textbox_components,
                        clear_modify_btn,
                        exec_modify_btn,
                        close_modify_btn,
                    ) = build_plan_input()
                
        # 绑定事件
        bind_ui_events(
            run_btn=run_btn,
            make_plan_btn=make_plan_btn,
            design_lci_btn=design_lci_btn,
            ref_materials_file=ref_materials_file,
            ref_data_file=ref_data_file,
            right_tabs=right_tabs,
            output_console=output_console,
            status=status,
            clear_btn=clear_btn,
            stop_btn=stop_btn,
            plan_input_tab=plan_input_tab,
            plan_output_tab=plan_output_tab,
            plan_modify_tab=plan_modify_tab,
            textbox_components=textbox_components,
            clear_fields_btn=clear_fields_btn,
            load_plan_btn=load_plan_btn,
            exec_plan_btn=exec_plan_btn,
            close_btn=close_btn,
            modify_textbox_components=modify_textbox_components,
            clear_modify_btn=clear_modify_btn,
            exec_modify_btn=exec_modify_btn,
            close_modify_btn=close_modify_btn
        )
        
    return demo, theme, css
