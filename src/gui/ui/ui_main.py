"""Backward-compatible entry: prefer ``gui.ui.app.build_ui`` for new code."""

from gui.ui.app import build_ui

__all__ = ["build_ui"]
