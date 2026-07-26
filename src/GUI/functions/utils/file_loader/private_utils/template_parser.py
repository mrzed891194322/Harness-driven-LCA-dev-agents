"""Compatibility adapter for the structured execution-plan template parser."""

from __future__ import annotations

from pathlib import Path

from functions.plan_editor import (
    PlanInputPart,
    PlanMarkdownPart,
    parse_execution_plan_template,
    render_template_parts,
)


def parse_plan_template(filepath: Path) -> list[dict]:
    """Return legacy block dictionaries backed by the declarative parser.

    Older file-loader callers still consume ``type=markdown/textbox`` blocks.
    Keeping this small adapter means they see the same fields as the current
    GUI without maintaining a second marker grammar.
    """
    template = parse_execution_plan_template(filepath)
    blocks: list[dict] = []
    for part in render_template_parts(template):
        if isinstance(part, PlanMarkdownPart):
            blocks.append({"type": "markdown", "content": part.content})
        else:
            field = part.field if isinstance(part, PlanInputPart) else None
            if field is None:  # pragma: no cover - defensive for future parts
                continue
            blocks.append(
                {
                    "type": "textbox",
                    "field_id": field.field_id,
                    "label": field.label,
                    "placeholder": field.placeholder,
                    "rows": field.rows,
                    "section": field.section,
                }
            )
    return blocks
