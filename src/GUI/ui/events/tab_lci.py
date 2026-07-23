import gradio as gr
from functions.utils.file_loader.main import main as run_file_loader_action


def bind_tab_lci_events(
    *,
    lci_mapping_tab: gr.Tab,
    lci_mapping_content_row: gr.Row,
    lci_mapping_warning_row: gr.Row,
    lci_mapping_toc_html: gr.HTML,
    lci_mapping_markdown: gr.Markdown,
    download_lci_mapping_btn: gr.DownloadButton,
):
    def check_and_update_lci_mapping_tab():
        import config
        from functions.utils.file_loader.private_utils.template_metadata import split_front_matter

        mapping_path = config.LCI_MAPPING_FILE_PATH
        metadata = run_file_loader_action("read_template_metadata", filepath=mapping_path)
        is_valid = (
            mapping_path.exists()
            and metadata.get("template_kind") == config.LCI_MAPPING_TEMPLATE_KIND
        )

        if is_valid:
            try:
                content = mapping_path.read_text(encoding="utf-8")
                _, body = split_front_matter(content)
                toc_html = run_file_loader_action(
                    "extract_toc",
                    filepath=mapping_path,
                    title="📋 映射目录导航",
                )
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    toc_html,
                    body,
                    gr.update(interactive=True, value=str(mapping_path)),
                )
            except Exception:
                pass

        return (
            gr.update(visible=False),
            gr.update(visible=True),
            "",
            "",
            gr.update(interactive=False, value=None),
        )

    lci_mapping_tab.select(
        fn=check_and_update_lci_mapping_tab,
        inputs=None,
        outputs=[
            lci_mapping_content_row,
            lci_mapping_warning_row,
            lci_mapping_toc_html,
            lci_mapping_markdown,
            download_lci_mapping_btn,
        ],
    )
