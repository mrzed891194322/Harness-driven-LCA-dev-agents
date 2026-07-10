from pathlib import Path
import gradio as gr
from ui.components.tab_terminal import build_tab_terminal
from ui.components.tab_plan import build_tab_plan
from ui.components.left_sidebar import build_left_sidebar
from ui.components.tab_initial import build_tab_initial
from ui.components.tab_lci import build_tab_lci
from ui.events import bind_ui_events


def build_ui() -> tuple[gr.Blocks, gr.themes.Soft, str, str]:
    theme = gr.themes.Soft(
        primary_hue="teal",
        secondary_hue="indigo",
        neutral_hue="slate"
    )
    
    assets_dir = Path(__file__).resolve().parent / "assets"
    css_dir = assets_dir / "css"
    css_files = [
        css_dir / "layout.css",
        css_dir / "left_sidebar.css",
        css_dir / "tab_terminal.css",
        css_dir / "tab_initial.css",
        css_dir / "tab_plan.css",
    ]
    css = "\n\n".join(
        css_file.read_text(encoding="utf-8")
        for css_file in css_files
        if css_file.exists()
    )

    js_dir = assets_dir / "js"
    js_files = [
        js_dir / "tab_navigation.js",
        js_dir / "status_monitor.js",
        js_dir / "terminal_scroll.js",
    ]
    js_code = "\n\n".join(
        js_file.read_text(encoding="utf-8")
        for js_file in js_files
        if js_file.exists()
    )

    with gr.Blocks(title="LCA Multi-agent UI", js=js_code) as demo:
        with gr.Row():
            gr.Markdown(
                """
                # 🌲 生命周期评估多智能体系统 - 控制面板
                ---
                """,
                elem_id="main-title"
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
                    _, output_console, status, clear_btn, stop_btn = build_tab_terminal()
                    
                    # 2. 项目初始化组件（初始不可见）
                    (
                        project_init_tab,
                        close_init_btn,
                        refresh_init_status_btn,
                        exec_init_btn,
                        env_status,
                        env_recheck_btn,
                        clean_status,
                        clean_check_btn,
                        clean_btn,
                        rag_status,
                        rag_check_btn,
                        rag_btn,
                        openlca_status,
                        openlca_recheck_btn,
                    ) = build_tab_initial()
                    
                    # 3. 拆分出的“计划输入”、“计划输出”和“计划修改”组件（初始不可见）
                    (
                        plan_input_tab,
                        plan_output_tab,
                        plan_modification_tab,
                        plan_template_container,
                        _plan_output_panel,
                        textbox_components,
                        clear_fields_btn,
                        load_plan_btn,
                        exec_plan_btn,
                        close_btn,
                        modify_textbox_pool,
                        clear_modify_btn,
                        load_modify_btn,
                        exec_modify_btn,
                        close_modify_btn,
                        download_plan_btn,
                        modify_plan_btn,
                        confirm_plan_btn,
                        close_output_btn,
                        plan_output_content_row,
                        plan_output_warning_row,
                        plan_output_toc_html,
                        plan_output_markdown,
                        plan_modify_content_row,
                        plan_modify_warning_row,
                        plan_modify_toc_html,
                        modify_markdown_pool
                    ) = build_tab_plan()

                    # 4. LCI 制定组件
                    (
                        lci_design_tab,
                        lci_mapping_tab,
                        close_lci_btn,
                        close_mapping_btn,
                        exec_lci_btn,
                        lci_mapping_content_row,
                        lci_mapping_warning_row,
                        lci_mapping_toc_html,
                        lci_mapping_markdown,
                        download_lci_mapping_btn,
                    ) = build_tab_lci()
                
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
            project_init_tab=project_init_tab,
            close_init_btn=close_init_btn,
            refresh_init_status_btn=refresh_init_status_btn,
            exec_init_btn=exec_init_btn,
            env_status=env_status,
            env_recheck_btn=env_recheck_btn,
            clean_status=clean_status,
            clean_check_btn=clean_check_btn,
            clean_btn=clean_btn,
            rag_status=rag_status,
            rag_check_btn=rag_check_btn,
            rag_btn=rag_btn,
            openlca_status=openlca_status,
            openlca_recheck_btn=openlca_recheck_btn,
            lci_design_tab=lci_design_tab,
            lci_mapping_tab=lci_mapping_tab,
            close_lci_btn=close_lci_btn,
            close_mapping_btn=close_mapping_btn,
            exec_lci_btn=exec_lci_btn,
            lci_mapping_content_row=lci_mapping_content_row,
            lci_mapping_warning_row=lci_mapping_warning_row,
            lci_mapping_toc_html=lci_mapping_toc_html,
            lci_mapping_markdown=lci_mapping_markdown,
            download_lci_mapping_btn=download_lci_mapping_btn,
            plan_input_tab=plan_input_tab,
            plan_output_tab=plan_output_tab,
            plan_modify_tab=plan_modification_tab,
            textbox_components=textbox_components,
            clear_fields_btn=clear_fields_btn,
            load_plan_btn=load_plan_btn,
            exec_plan_btn=exec_plan_btn,
            close_btn=close_btn,
            modify_textbox_components=modify_textbox_pool,
            clear_modify_btn=clear_modify_btn,
            load_modify_btn=load_modify_btn,
            exec_modify_btn=exec_modify_btn,
            close_modify_btn=close_modify_btn,
            download_plan_btn=download_plan_btn,
            modify_plan_btn=modify_plan_btn,
            confirm_plan_btn=confirm_plan_btn,
            close_output_btn=close_output_btn,
            plan_output_content_row=plan_output_content_row,
            plan_output_warning_row=plan_output_warning_row,
            plan_output_toc_html=plan_output_toc_html,
            plan_output_markdown=plan_output_markdown,
            plan_modify_content_row=plan_modify_content_row,
            plan_modify_warning_row=plan_modify_warning_row,
            plan_modify_toc_html=plan_modify_toc_html,
            modify_markdown_pool=modify_markdown_pool
        )
        
    return demo, theme, css, js_code
