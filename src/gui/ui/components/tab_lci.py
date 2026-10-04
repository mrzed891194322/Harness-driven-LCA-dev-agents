import gradio as gr

from gui.i18n import t


def build_tab_lci(
    locale: str,
) -> tuple[
    gr.Tab,
    gr.Button,
    gr.JSON,
    gr.Markdown,
    gr.DownloadButton,
    gr.JSON,
    gr.Markdown,
    gr.DownloadButton,
    gr.Button,
]:
    """Build the mounted work-details tab with two stacked JSON trees."""
    from gui import config

    bom_relative = config.EXTRACTED_BOM_RELATIVE_PATH.as_posix()
    mapping_relative = config.PROCESS_MAPPING_RELATIVE_PATH.as_posix()
    with gr.Tab(t("tab.lci", locale), id="lci_mapping_tab") as lci_mapping_tab:
        with gr.Column(
            elem_id="lci-mapping-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            with gr.Column(
                elem_id="lci-mapping-panel",
                elem_classes=["inner-panel-grid"],
            ):
                gr.Markdown(t("lci.heading", locale))
                with gr.Column(
                    elem_id="work-details-scroll",
                    elem_classes=["panel-scroll-container"],
                ):
                    gr.Markdown(
                        t("lci.bom_heading", locale, path=bom_relative),
                        elem_id="work-details-bom-heading",
                    )
                    bom_json = gr.JSON(
                        value=None,
                        show_label=False,
                        open=True,
                        visible=False,
                        max_height=400,
                        elem_id="work-details-bom-json",
                    )
                    bom_warning = gr.Markdown(
                        t("lci.bom_missing", locale, path=bom_relative),
                        visible=True,
                        elem_id="work-details-bom-warning",
                    )

                    gr.Markdown(
                        t("lci.mapping_heading", locale, path=mapping_relative),
                        elem_id="work-details-mapping-heading",
                    )
                    mapping_json = gr.JSON(
                        value=None,
                        show_label=False,
                        open=True,
                        visible=False,
                        max_height=400,
                        elem_id="work-details-mapping-json",
                    )
                    mapping_warning = gr.Markdown(
                        t("lci.mapping_missing", locale, path=mapping_relative),
                        visible=True,
                        elem_id="work-details-mapping-warning",
                    )

                with gr.Row(
                    elem_id="lci-mapping-actions-row",
                    elem_classes=["panel-actions-row"],
                ):
                    close_mapping_btn = gr.Button(
                        t("lci.close", locale),
                        variant="secondary",
                        elem_id="close-lci-mapping-btn",
                    )
                    download_bom_btn = gr.DownloadButton(
                        t("lci.download_bom", locale),
                        variant="secondary",
                        interactive=False,
                        elem_id="download-extracted-bom-btn",
                    )
                    download_mapping_btn = gr.DownloadButton(
                        t("lci.download_mapping", locale),
                        variant="secondary",
                        interactive=False,
                        elem_id="download-process-mapping-btn",
                    )
                    modify_lci_btn = gr.Button(
                        t("lci.modify", locale),
                        variant="primary",
                        interactive=False,
                        elem_id="modify-lci-inventory-btn",
                    )

    return (
        lci_mapping_tab,
        close_mapping_btn,
        bom_json,
        bom_warning,
        download_bom_btn,
        mapping_json,
        mapping_warning,
        download_mapping_btn,
        modify_lci_btn,
    )
