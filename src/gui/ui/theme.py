"""Gradio theme configuration aligned with ``assets/css/tokens.css``."""

from __future__ import annotations

from typing import Any

import gradio.themes as gr_themes


def build_gradio_theme() -> Any:
    """Return the Soft theme with LCA-specific radii and primary accents."""
    return (
        gr_themes.Soft(
            primary_hue=gr_themes.colors.teal,
            secondary_hue=gr_themes.colors.indigo,
            neutral_hue=gr_themes.colors.slate,
        )
        .set(
            button_large_radius="10px",
            button_medium_radius="8px",
            button_small_radius="6px",
            button_primary_background_fill="*primary_500",
            button_primary_background_fill_hover="*primary_600",
            button_primary_text_color="white",
            button_secondary_background_fill="*neutral_50",
            button_secondary_background_fill_hover="*neutral_100",
            button_secondary_text_color="*neutral_800",
            block_background_fill="*neutral_50",
            block_border_color="*neutral_200",
            block_border_width="1px",
            block_radius="10px",
            block_shadow="*shadow_drop_sm",
            input_background_fill="*neutral_50",
            input_border_color="*neutral_200",
            input_radius="8px",
            body_background_fill="*neutral_50",
            body_text_color="*neutral_800",
            body_text_color_subdued="*neutral_600",
        )
    )
