import gradio as gr

from gui.i18n import t


def build_left_sidebar(
    locale: str,
) -> tuple[
    gr.Button,
    gr.Button,
    gr.File,
]:
    """
    构建左侧栏：文件交换区与快捷操作区。
    """
    with gr.Group(elem_id="file-exchange-section"):
        gr.Markdown(
            f"{t('sidebar.file_heading', locale)}\n{t('sidebar.file_desc', locale)}"
        )
        ref_upload_file = gr.File(
            label=t("sidebar.upload_label", locale),
            file_count="multiple",
            interactive=True,
            elem_id="reference-upload",
        )

    with gr.Column(elem_id="quick-actions-section"):
        gr.Markdown(
            f"{t('sidebar.actions_heading', locale)}\n{t('sidebar.actions_desc', locale)}"
        )

        open_init_btn = gr.Button(
            t("sidebar.open_settings", locale),
            variant="secondary",
            size="lg",
            interactive=True,
            elem_id="quick-action-project",
            elem_classes=["quick-action-btn"],
        )
        start_lca_btn = gr.Button(
            t("sidebar.start_lca", locale),
            variant="secondary",
            size="lg",
            interactive=True,
            elem_id="quick-action-start-lca",
            elem_classes=["quick-action-btn"],
        )

    return (
        open_init_btn,
        start_lca_btn,
        ref_upload_file,
    )
