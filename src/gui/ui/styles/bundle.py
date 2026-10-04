"""Ordered static asset bundles for the Gradio shell."""

from __future__ import annotations

from pathlib import Path

_UI_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = _UI_ROOT / "assets"
CSS_DIR = ASSETS_DIR / "css"
JS_DIR = ASSETS_DIR / "js"

# Load order: tokens first, then shared layout, then feature sheets.
CSS_BUNDLE: tuple[str, ...] = (
    "tokens.css",
    "layout.css",
    "header.css",
    "left_sidebar.css",
    "tab_terminal.css",
    "tab_initial.css",
    "render_mdfile.css",
    "tab_plan.css",
)

JS_BUNDLE: tuple[str, ...] = (
    "tab_navigation.js",
    "status_monitor.js",
    "terminal_scroll.js",
)


def runtime_css_variables() -> str:
    """Inject font stacks from ``gui.config`` (not stored in static CSS files)."""
    from gui import config

    return (
        ":root {\n"
        f"    --gui-ui-font: {config.GUI_UI_FONT_FAMILY};\n"
        f"    --academic-serif-font: {config.GUI_FONT_FAMILY};\n"
        f"    --gui-monospace-font: {config.GUI_MONO_FONT_FAMILY};\n"
        "}"
    )


def bundle_css() -> str:
    parts: list[str] = [runtime_css_variables()]
    for name in CSS_BUNDLE:
        path = CSS_DIR / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def bundle_js() -> str:
    parts: list[str] = []
    for name in JS_BUNDLE:
        path = JS_DIR / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)
