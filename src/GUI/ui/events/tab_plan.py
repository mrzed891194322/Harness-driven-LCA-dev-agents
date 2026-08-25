from __future__ import annotations

import gradio as gr

from functions.plan_editor import (
    MAX_PLAN_INPUTS,
    PlanTemplate,
    PlanTemplateError,
    is_plan_ready,
    parse_execution_plan_text,
    parse_execution_plan_template,
    read_uploaded_plan,
)
from functions.settings.check_status import execution_ready
from ui.components.render_mdfile import (
    MarkdownDocumentView,
    document_output_components,
    loaded_document_outputs,
    unavailable_document_outputs,
    validate_document_view_pool,
)


def bind_tab_plan_events(
    *,
    start_lca_btn: gr.Button,
    plan_view: MarkdownDocumentView,
    close_plan_btn: gr.Button,
    upload_plan_btn: gr.UploadButton,
    execute_lca_btn: gr.Button,
    right_tabs: gr.Tabs,
    plan_ready_state: gr.State,
    init_check_ok_state: gr.State,
) -> None:
    """Bind default loading, upload staging and the execution readiness gate."""

    validate_document_view_pool(plan_view)

    def _readiness(
        template: PlanTemplate,
        values: list[object],
        init_ok: object,
    ):
        active_values = values[: len(template.fields)]
        ready = (
            is_plan_ready(active_values)
            if template.fields
            else bool(template.source.strip())
        )
        return ready, gr.update(
            interactive=execution_ready(init_ok, ready)
        )

    def _loaded_document_outputs(
        template: PlanTemplate,
        source_label: str,
        init_ok: object,
    ):
        ready, button = _readiness(
            template,
            list(template.values),
            init_ok,
        )
        return (
            *loaded_document_outputs(
                plan_view,
                template,
                source_label=source_label,
            ),
            ready,
            button,
        )

    def _default_error_outputs(message: str):
        return (
            *unavailable_document_outputs(plan_view, message),
            False,
            gr.update(interactive=False),
        )

    def load_plan_panel(init_ok):
        import config

        try:
            template = parse_execution_plan_template(
                config.PLAN_INPUT_TEMPLATE_PATH
            )
        except (OSError, UnicodeError, ValueError) as exc:
            document_outputs = _default_error_outputs(str(exc))
        else:
            document_outputs = _loaded_document_outputs(
                template,
                "默认模板",
                init_ok,
            )
        return (
            gr.update(selected="plan_editor_tab"),
            *document_outputs,
        )

    open_outputs = [
        right_tabs,
        *document_output_components(plan_view),
        plan_ready_state,
        execute_lca_btn,
    ]
    start_lca_btn.click(
        fn=load_plan_panel,
        inputs=[init_check_ok_state],
        outputs=open_outputs,
        queue=False,
        show_progress="hidden",
        js="window.guiOpenPlanMode",
    )

    def update_form_readiness(*arguments):
        extra_count = 2
        if len(arguments) < MAX_PLAN_INPUTS + extra_count:
            return False, gr.update(interactive=False)
        values = list(arguments[:MAX_PLAN_INPUTS])
        source_text, init_ok = arguments[MAX_PLAN_INPUTS:]
        if not source_text:
            return False, gr.update(interactive=False)
        try:
            template = parse_execution_plan_text(source_text)
        except PlanTemplateError:
            return False, gr.update(interactive=False)
        return _readiness(template, values, init_ok)

    readiness_inputs = [
        *plan_view.inputs,
        plan_view.source_state,
        init_check_ok_state,
    ]
    for plan_input in plan_view.inputs:
        plan_input.input(
            fn=update_form_readiness,
            inputs=readiness_inputs,
            outputs=[plan_ready_state, execute_lca_btn],
        )

    def stage_uploaded_plan(file_obj, init_ok):
        try:
            text = read_uploaded_plan(file_obj)
            template = parse_execution_plan_text(
                text,
                source=getattr(file_obj, "name", "<uploaded-plan.md>"),
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise gr.Error(f"上传计划失败，当前页面未改变：{exc}") from exc

        return _loaded_document_outputs(
            template,
            "上传计划",
            init_ok,
        )

    upload_plan_btn.upload(
        fn=stage_uploaded_plan,
        inputs=[
            upload_plan_btn,
            init_check_ok_state,
        ],
        outputs=[
            *document_output_components(plan_view),
            plan_ready_state,
            execute_lca_btn,
        ],
    )

    close_plan_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiClosePanel",
    )
