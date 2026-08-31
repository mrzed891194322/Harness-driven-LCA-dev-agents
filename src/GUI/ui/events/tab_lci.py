from __future__ import annotations

import json
from pathlib import Path

import gradio as gr


def read_work_details_json(path: Path) -> tuple[object | None, str | None]:
    """Load a work-details JSON file.

    Returns ``(payload, None)`` on success, or ``(None, warning_markdown)``
    when the file is missing or not valid JSON.
    """
    import config

    try:
        relative = path.relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        relative = path.as_posix()

    if not path.is_file():
        return None, f"### ⚠️ 缺少文件\n\n未找到 `{relative}`。"

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return (
            None,
            (
                f"### ⚠️ 无法解析 JSON\n\n`{relative}` 不是有效 JSON"
                f"（{exc}）。"
            ),
        )
    return payload, None


def _json_section_outputs(path: Path) -> tuple:
    payload, warning = read_work_details_json(path)
    if warning is not None:
        return (
            gr.update(value=None, visible=False),
            gr.update(visible=True, value=warning),
            gr.update(interactive=False, value=None),
        )
    return (
        gr.update(value=payload, visible=True),
        gr.update(visible=False),
        gr.update(interactive=True, value=str(path)),
    )


def bind_tab_lci_events(
    *,
    show_lci_btn: gr.Button,
    close_lci_mapping_btn: gr.Button,
    right_tabs: gr.Tabs,
    bom_json: gr.JSON,
    bom_warning: gr.Markdown,
    download_bom_btn: gr.DownloadButton,
    mapping_json: gr.JSON,
    mapping_warning: gr.Markdown,
    download_mapping_btn: gr.DownloadButton,
) -> None:
    def open_work_details():
        import config

        return (
            *_json_section_outputs(config.EXTRACTED_BOM_FILE_PATH),
            *_json_section_outputs(config.PROCESS_MAPPING_FILE_PATH),
            gr.update(selected="lci_mapping_tab"),
        )

    show_lci_btn.click(
        fn=open_work_details,
        inputs=None,
        outputs=[
            bom_json,
            bom_warning,
            download_bom_btn,
            mapping_json,
            mapping_warning,
            download_mapping_btn,
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
