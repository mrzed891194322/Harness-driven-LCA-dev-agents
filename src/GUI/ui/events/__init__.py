import gradio as gr

from ui.events.left_sidebar import bind_left_sidebar_events
from ui.events.tab_initial import bind_tab_initial_events
from ui.events.tab_lci import bind_tab_lci_events
from ui.events.tab_terminal import bind_tab_terminal_events


def bind_ui_events(
    *,
    run_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    right_tabs: gr.Tabs,
    output_console: gr.Textbox,
    status: gr.Textbox,
    clear_btn: gr.Button,
    stop_btn: gr.Button,
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
    lci_mapping_tab: gr.Tab,
    lci_mapping_content_row: gr.Row,
    lci_mapping_warning_row: gr.Row,
    lci_mapping_toc_html: gr.HTML,
    lci_mapping_markdown: gr.Markdown,
    download_lci_mapping_btn: gr.DownloadButton,
) -> None:
    """Bind events for the currently supported GUI features.

    Plan creation/modification and LCI design are intentionally not bound:
    their backend commands were removed from the current workflow.  Their
    legacy components remain available in the layout but are disabled.
    """
    bind_left_sidebar_events(
        run_btn=run_btn,
        right_tabs=right_tabs,
        close_init_btn=close_init_btn,
    )

    bind_tab_terminal_events(
        clear_btn=clear_btn,
        stop_btn=stop_btn,
        output_console=output_console,
        status=status,
    )

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

    # The mapping report is read-only and does not invoke the removed LCI
    # design command, so its tab can continue to display existing output.
    bind_tab_lci_events(
        lci_mapping_tab=lci_mapping_tab,
        lci_mapping_content_row=lci_mapping_content_row,
        lci_mapping_warning_row=lci_mapping_warning_row,
        lci_mapping_toc_html=lci_mapping_toc_html,
        lci_mapping_markdown=lci_mapping_markdown,
        download_lci_mapping_btn=download_lci_mapping_btn,
    )
