import gradio as gr

from functions.plan_editor import parse_markdown_document_text
from ui.components.render_mdfile import (
    MarkdownDocumentView,
    cleared_document_outputs,
    document_output_components,
    loaded_document_outputs,
)


def bind_tab_lci_events(
    *,
    show_lci_btn: gr.Button,
    close_lci_mapping_btn: gr.Button,
    right_tabs: gr.Tabs,
    lci_mapping_view: MarkdownDocumentView,
    lci_mapping_warning_row: gr.Row,
    download_lci_mapping_btn: gr.DownloadButton,
) -> None:
    def check_and_update_lci_mapping_tab():
        import config

        mapping_path = config.LCI_MAPPING_FILE_PATH
        try:
            content = mapping_path.read_text(encoding="utf-8-sig")
            document = parse_markdown_document_text(
                content,
                source=mapping_path,
            )
        except (OSError, UnicodeError, ValueError):
            return (
                *cleared_document_outputs(lci_mapping_view),
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(interactive=False, value=None),
            )

        return (
            *loaded_document_outputs(
                lci_mapping_view,
                document,
            ),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(interactive=True, value=str(mapping_path)),
        )

    def open_lci_mapping():
        return (
            *check_and_update_lci_mapping_tab(),
            gr.update(selected="lci_mapping_tab"),
        )

    show_lci_btn.click(
        fn=open_lci_mapping,
        inputs=None,
        outputs=[
            *document_output_components(lci_mapping_view),
            lci_mapping_view.content_row,
            lci_mapping_warning_row,
            download_lci_mapping_btn,
            right_tabs,
        ],
        js="window.guiOpenLciReportMode",
        queue=False,
        show_progress="hidden",
    )

    close_lci_mapping_btn.click(
        fn=lambda: gr.update(selected="lca_result_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiCloseLciReportPanel",
        queue=False,
        show_progress="hidden",
    )
