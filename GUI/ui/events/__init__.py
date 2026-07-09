import gradio as gr
from ui.events.left_sidebar import bind_left_sidebar_events
from ui.events.tab_terminal import bind_tab_terminal_events
from ui.events.tab_initial import bind_tab_initial_events
from ui.events.tab_plan import bind_tab_plan_events
from ui.events.tab_lci import bind_tab_lci_events


def bind_ui_events(
    # Left sidebar components
    run_btn: gr.Button,
    make_plan_btn: gr.Button,
    design_lci_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    # Right panel components
    right_tabs: gr.Tabs,
    output_console: gr.Textbox,
    status: gr.Textbox,
    clear_btn: gr.Button,
    stop_btn: gr.Button,
    # Plan input components
    plan_input_tab: gr.Tab,
    plan_output_tab: gr.Tab,
    plan_modify_tab: gr.Tab,
    textbox_components: list[gr.Textbox],
    clear_fields_btn: gr.Button,
    load_plan_btn: gr.UploadButton,
    exec_plan_btn: gr.Button,
    close_btn: gr.Button,
    # Plan modification components
    modify_textbox_components: list[gr.Textbox],
    clear_modify_btn: gr.Button,
    exec_modify_btn: gr.Button,
    close_modify_btn: gr.Button,
    download_plan_btn: gr.DownloadButton,
    modify_plan_btn: gr.Button,
    confirm_plan_btn: gr.Button,
    close_output_btn: gr.Button,
    plan_output_content_row: gr.Row,
    plan_output_warning_row: gr.Row,
    plan_output_toc_html: gr.HTML,
    plan_output_markdown: gr.Markdown,
    plan_modify_content_row: gr.Row,
    plan_modify_warning_row: gr.Row,
    plan_modify_toc_html: gr.HTML,
    modify_markdown_pool: list[gr.Markdown],
    # Project init components
    project_init_tab: gr.Tab,
    close_init_btn: gr.Button,
    refresh_init_status_btn: gr.Button,
    exec_init_btn: gr.Button,
    env_status: gr.Markdown,
    env_recheck_btn: gr.Button,
    clean_status: gr.Markdown,
    clean_check_btn: gr.Button | None,
    clean_btn: gr.Button,
    rag_status: gr.Markdown,
    rag_check_btn: gr.Button | None,
    rag_btn: gr.Button,
    openlca_status: gr.Markdown,
    openlca_recheck_btn: gr.Button,
    # LCI design components
    lci_design_tab: gr.Tab,
    lci_mapping_tab: gr.Tab,
    close_lci_btn: gr.Button,
    close_mapping_btn: gr.Button,
    exec_lci_btn: gr.Button,
    lci_mapping_content_row: gr.Row,
    lci_mapping_warning_row: gr.Row,
    lci_mapping_toc_html: gr.HTML,
    lci_mapping_markdown: gr.Markdown,
    download_lci_mapping_btn: gr.DownloadButton,
):
    """
    绑定 Gradio 的按钮点击与上传等所有 UI 交互事件。
    """
    # 1. 绑定导航与侧栏/关闭按钮事件
    bind_left_sidebar_events(
        run_btn=run_btn,
        make_plan_btn=make_plan_btn,
        design_lci_btn=design_lci_btn,
        right_tabs=right_tabs,
        close_btn=close_btn,
        close_modify_btn=close_modify_btn,
        close_output_btn=close_output_btn,
        close_init_btn=close_init_btn,
        close_lci_btn=close_lci_btn,
        close_mapping_btn=close_mapping_btn,
    )

    # 2. 绑定终端日志清空与停止逻辑
    bind_tab_terminal_events(
        clear_btn=clear_btn,
        stop_btn=stop_btn,
        output_console=output_console,
        status=status,
    )

    # 3. 绑定项目初始化面板交互逻辑
    bind_tab_initial_events(
        refresh_init_status_btn=refresh_init_status_btn,
        env_recheck_btn=env_recheck_btn,
        openlca_recheck_btn=openlca_recheck_btn,
        clean_check_btn=clean_check_btn,
        rag_check_btn=rag_check_btn,
        clean_btn=clean_btn,
        rag_btn=rag_btn,
        exec_init_btn=exec_init_btn,
        ref_materials_file=ref_materials_file,
        ref_data_file=ref_data_file,
        env_status=env_status,
        clean_status=clean_status,
        rag_status=rag_status,
        openlca_status=openlca_status,
        output_console=output_console,
        status=status,
    )

    # 4. 绑定工作计划相关交互逻辑
    bind_tab_plan_events(
        clear_fields_btn=clear_fields_btn,
        load_plan_btn=load_plan_btn,
        exec_plan_btn=exec_plan_btn,
        clear_modify_btn=clear_modify_btn,
        exec_modify_btn=exec_modify_btn,
        modify_plan_btn=modify_plan_btn,
        confirm_plan_btn=confirm_plan_btn,
        download_plan_btn=download_plan_btn,
        plan_output_tab=plan_output_tab,
        plan_modify_tab=plan_modify_tab,
        textbox_components=textbox_components,
        modify_textbox_components=modify_textbox_components,
        right_tabs=right_tabs,
        output_console=output_console,
        status=status,
        plan_output_content_row=plan_output_content_row,
        plan_output_warning_row=plan_output_warning_row,
        plan_output_toc_html=plan_output_toc_html,
        plan_output_markdown=plan_output_markdown,
        plan_modify_content_row=plan_modify_content_row,
        plan_modify_warning_row=plan_modify_warning_row,
        plan_modify_toc_html=plan_modify_toc_html,
        modify_markdown_pool=modify_markdown_pool,
    )

    # 5. 绑定清单制定逻辑
    bind_tab_lci_events(
        lci_mapping_tab=lci_mapping_tab,
        exec_lci_btn=exec_lci_btn,
        output_console=output_console,
        status=status,
        lci_mapping_content_row=lci_mapping_content_row,
        lci_mapping_warning_row=lci_mapping_warning_row,
        lci_mapping_toc_html=lci_mapping_toc_html,
        lci_mapping_markdown=lci_mapping_markdown,
        download_lci_mapping_btn=download_lci_mapping_btn,
    )
