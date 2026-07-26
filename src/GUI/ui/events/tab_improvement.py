from __future__ import annotations

import gradio as gr

from functions.plan_editor import (
    parse_execution_plan_text,
    parse_execution_plan_template,
    read_uploaded_markdown,
)
from ui.components.render_mdfile import (
    MarkdownDocumentView,
    document_output_components,
    loaded_document_outputs,
    unavailable_document_outputs,
    validate_document_view_pool,
)


def bind_tab_improvement_events(
    *,
    modify_rerun_btn: gr.Button,
    improvement_view: MarkdownDocumentView,
    close_improvement_btn: gr.Button,
    upload_improvement_btn: gr.UploadButton,
    right_tabs: gr.Tabs,
) -> None:
    """Bind independent default loading, upload staging and close behavior."""
    validate_document_view_pool(improvement_view)
    document_outputs = document_output_components(improvement_view)

    def load_improvement_panel():
        import config

        try:
            template = parse_execution_plan_template(
                config.REVISE_TEMPLATE_PATH
            )
        except (OSError, UnicodeError, ValueError) as exc:
            updates = unavailable_document_outputs(
                improvement_view,
                str(exc),
            )
        else:
            updates = loaded_document_outputs(
                improvement_view,
                template,
                source_label="默认模板",
            )
        return gr.update(selected="lca_improvement_tab"), *updates

    modify_rerun_btn.click(
        fn=load_improvement_panel,
        inputs=None,
        outputs=[right_tabs, *document_outputs],
        queue=False,
        show_progress="hidden",
        js="window.guiOpenImprovementMode",
    )

    def stage_uploaded_improvement(file_obj):
        try:
            text = read_uploaded_markdown(
                file_obj,
                document_label="改进方案",
            )
            template = parse_execution_plan_text(
                text,
                source=getattr(
                    file_obj,
                    "name",
                    "<uploaded-revise.md>",
                ),
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise gr.Error(
                f"上传改进方案失败，当前页面未改变：{exc}"
            ) from exc

        return loaded_document_outputs(
            improvement_view,
            template,
            source_label="上传改进方案",
        )

    upload_improvement_btn.upload(
        fn=stage_uploaded_improvement,
        inputs=upload_improvement_btn,
        outputs=document_outputs,
    )

    def close_improvement_panel():
        return gr.update(selected="lca_result_tab")

    close_improvement_btn.click(
        fn=close_improvement_panel,
        inputs=None,
        outputs=right_tabs,
        queue=False,
        show_progress="hidden",
        js="window.guiCloseImprovementPanel",
    )
