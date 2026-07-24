from pathlib import Path
import gradio as gr
from ui.components.tab_terminal import build_tab_terminal
from ui.components.tab_plan import build_tab_plan
from ui.components.left_sidebar import build_left_sidebar
from ui.components.tab_initial import build_tab_initial
from ui.components.tab_lci import build_tab_lci
from ui.components.tab_result import build_tab_result
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

    with gr.Blocks(title="LCA Multi-agent UI") as demo:
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
                    start_lca_btn,
                    clear_file_inputs_btn,
                    ref_materials_file,
                    ref_data_file
                ) = build_left_sidebar()
                
            with gr.Column(scale=2, elem_id="right-panel"):
                with gr.Tabs(elem_id="right-tabs") as right_tabs:
                    # 项目初始化始终位于最左侧，并作为默认 Tab。
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

                    _, output_console, status, clear_btn, stop_btn = build_tab_terminal()

                    (
                        result_tab,
                        result_heading,
                        success_panel,
                        failure_panel,
                        failure_markdown,
                        report_markdown,
                        report_warning,
                        download_report_btn,
                        show_lci_btn,
                        modify_rerun_btn,
                    ) = build_tab_result()

                    (
                        _plan_tab,
                        plan_markdowns,
                        plan_toc,
                        plan_status,
                        plan_source_state,
                        plan_inputs,
                        close_plan_btn,
                        upload_plan_btn,
                        execute_lca_btn,
                    ) = build_tab_plan()

                    # 按需显示的只读 LCI 映射组件。
                    (
                        lci_mapping_tab,
                        _close_mapping_btn,
                        lci_mapping_content_row,
                        lci_mapping_warning_row,
                        lci_mapping_toc_html,
                        lci_mapping_markdown,
                        download_lci_mapping_btn,
                        _modify_lci_btn,
                    ) = build_tab_lci()

        run_result_state = gr.State(value=None)
        env_gate_state = gr.State(value=False)
        openlca_gate_state = gr.State(value=False)
        plan_ready_state = gr.State(value=False)

        # 绑定事件
        bind_ui_events(
            run_btn=run_btn,
            start_lca_btn=start_lca_btn,
            execute_lca_btn=execute_lca_btn,
            clear_file_inputs_btn=clear_file_inputs_btn,
            ref_materials_file=ref_materials_file,
            ref_data_file=ref_data_file,
            right_tabs=right_tabs,
            output_console=output_console,
            status=status,
            clear_btn=clear_btn,
            stop_btn=stop_btn,
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
            lci_mapping_tab=lci_mapping_tab,
            lci_mapping_content_row=lci_mapping_content_row,
            lci_mapping_warning_row=lci_mapping_warning_row,
            lci_mapping_toc_html=lci_mapping_toc_html,
            lci_mapping_markdown=lci_mapping_markdown,
            download_lci_mapping_btn=download_lci_mapping_btn,
            run_result_state=run_result_state,
            result_tab=result_tab,
            result_heading=result_heading,
            success_panel=success_panel,
            failure_panel=failure_panel,
            failure_markdown=failure_markdown,
            show_lci_btn=show_lci_btn,
            modify_rerun_btn=modify_rerun_btn,
            plan_markdowns=plan_markdowns,
            plan_toc=plan_toc,
            plan_status=plan_status,
            plan_inputs=plan_inputs,
            plan_source_state=plan_source_state,
            close_plan_btn=close_plan_btn,
            upload_plan_btn=upload_plan_btn,
            report_markdown=report_markdown,
            report_warning=report_warning,
            download_report_btn=download_report_btn,
            env_gate_state=env_gate_state,
            openlca_gate_state=openlca_gate_state,
            plan_ready_state=plan_ready_state,
        )
        
    return demo, theme, css, js_code
