import gradio as gr

from ui.components.render_mdfile import MarkdownDocumentView
from ui.events.left_sidebar import bind_left_sidebar_events
from ui.events.tab_improvement import bind_tab_improvement_events
from ui.events.tab_initial import bind_tab_initial_events
from ui.events.tab_lci import bind_tab_lci_events
from ui.events.tab_plan import bind_tab_plan_events
from ui.events.tab_terminal import bind_tab_terminal_events
from ui.events.tab_result import bind_tab_result_events


def bind_ui_events(
    *,
    open_init_btn: gr.Button,
    start_lca_btn: gr.Button,
    execute_lca_btn: gr.Button,
    view_lca_result_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    right_tabs: gr.Tabs,
    output_console: gr.Textbox,
    status: gr.Textbox,
    clear_btn: gr.Button,
    stop_btn: gr.Button,
    init_check_btn: gr.Button,
    init_check_status_values: list[gr.Markdown],
    agent_radio: gr.Radio,
    agent_check_btn: gr.Button,
    dev_gui_port: gr.Number,
    dev_openlca_port: gr.Number,
    dev_ports_save_btn: gr.Button,
    close_lci_mapping_btn: gr.Button,
    lci_mapping_view: MarkdownDocumentView,
    lci_mapping_warning_row: gr.Row,
    download_lci_mapping_btn: gr.DownloadButton,
    run_result_state: gr.State,
    result_heading: gr.Markdown,
    success_panel: gr.Column,
    failure_panel: gr.Column,
    failure_markdown: gr.Markdown,
    show_lci_btn: gr.Button,
    modify_rerun_btn: gr.Button,
    improvement_view: MarkdownDocumentView,
    close_improvement_btn: gr.Button,
    upload_improvement_btn: gr.UploadButton,
    execute_improvement_btn: gr.Button,
    plan_view: MarkdownDocumentView,
    close_plan_btn: gr.Button,
    upload_plan_btn: gr.UploadButton,
    report_view: MarkdownDocumentView,
    report_warning: gr.Markdown,
    download_report_btn: gr.DownloadButton,
    init_check_ok_state: gr.State,
    plan_ready_state: gr.State,
    improvement_ready_state: gr.State,
) -> None:
    """Bind events for the currently supported GUI features."""
    bind_left_sidebar_events(
        open_init_btn=open_init_btn,
        right_tabs=right_tabs,
        agent_radio=agent_radio,
        dev_gui_port=dev_gui_port,
        dev_openlca_port=dev_openlca_port,
    )

    bind_tab_terminal_events(
        clear_btn=clear_btn,
        stop_btn=stop_btn,
        output_console=output_console,
        status=status,
    )

    bind_tab_initial_events(
        init_check_btn=init_check_btn,
        init_check_status_values=init_check_status_values,
        agent_check_btn=agent_check_btn,
        dev_ports_save_btn=dev_ports_save_btn,
        ref_materials_file=ref_materials_file,
        ref_data_file=ref_data_file,
        agent_radio=agent_radio,
        dev_gui_port=dev_gui_port,
        dev_openlca_port=dev_openlca_port,
        execute_lca_btn=execute_lca_btn,
        execute_improvement_btn=execute_improvement_btn,
        init_check_ok_state=init_check_ok_state,
        plan_ready_state=plan_ready_state,
        improvement_ready_state=improvement_ready_state,
    )

    bind_tab_plan_events(
        start_lca_btn=start_lca_btn,
        plan_view=plan_view,
        close_plan_btn=close_plan_btn,
        upload_plan_btn=upload_plan_btn,
        execute_lca_btn=execute_lca_btn,
        right_tabs=right_tabs,
        plan_ready_state=plan_ready_state,
        init_check_ok_state=init_check_ok_state,
    )

    revision_execute_event = bind_tab_improvement_events(
        modify_rerun_btn=modify_rerun_btn,
        improvement_view=improvement_view,
        close_improvement_btn=close_improvement_btn,
        upload_improvement_btn=upload_improvement_btn,
        execute_improvement_btn=execute_improvement_btn,
        right_tabs=right_tabs,
        init_check_ok_state=init_check_ok_state,
        improvement_ready_state=improvement_ready_state,
        output_console=output_console,
        status=status,
        run_result_state=run_result_state,
    )

    bind_tab_lci_events(
        show_lci_btn=show_lci_btn,
        close_lci_mapping_btn=close_lci_mapping_btn,
        right_tabs=right_tabs,
        lci_mapping_view=lci_mapping_view,
        lci_mapping_warning_row=lci_mapping_warning_row,
        download_lci_mapping_btn=download_lci_mapping_btn,
    )

    bind_tab_result_events(
        view_lca_result_btn=view_lca_result_btn,
        execute_lca_btn=execute_lca_btn,
        plan_view=plan_view,
        report_view=report_view,
        plan_ready_state=plan_ready_state,
        improvement_ready_state=improvement_ready_state,
        execute_improvement_btn=execute_improvement_btn,
        revision_execute_event=revision_execute_event,
        init_check_ok_state=init_check_ok_state,
        output_console=output_console,
        status=status,
        run_result_state=run_result_state,
        right_tabs=right_tabs,
        result_heading=result_heading,
        success_panel=success_panel,
        failure_panel=failure_panel,
        failure_markdown=failure_markdown,
        report_warning=report_warning,
        download_report_btn=download_report_btn,
    )
