"""顶部标题栏：标题、项目链接与作者信息。

需要改标题栏文字或链接时只改本文件顶部常量；界面语言相关的标题与标签在 ``gui/i18n/messages.py``。
样式在 ``ui/assets/css/header.css``。
"""

from __future__ import annotations

from html import escape

import gradio as gr

from gui.i18n import t

GITHUB_URL = "https://github.com/mrzed891194322/Harness-driven-LCA-dev-agents"
AUTHOR_NAME = "Du Yuan"
AUTHOR_EMAIL = "yuandu0214@outlook.com"


def render_header_html(
    locale: str,
    *,
    github_url: str = GITHUB_URL,
    author_name: str = AUTHOR_NAME,
    author_email: str = AUTHOR_EMAIL,
) -> str:
    link_attrs = 'target="_blank" rel="noopener noreferrer"'
    title = t("header.title", locale)
    github_label = t("header.github", locale)
    author_prefix = t("header.author_prefix", locale)
    return (
        '<header class="app-header">'
        f'<h1 class="app-header-title">{escape(title)}</h1>'
        '<div class="app-header-meta">'
        f'<a class="app-header-link" href="{escape(github_url)}" {link_attrs}>'
        f"{escape(github_label)}</a>"
        '<span class="app-header-sep" aria-hidden="true">·</span>'
        f'<span class="app-header-author">{escape(author_prefix)}{escape(author_name)}</span>'
        '<span class="app-header-sep" aria-hidden="true">·</span>'
        f'<a class="app-header-link" href="mailto:{escape(author_email)}">'
        f"{escape(author_email)}</a>"
        "</div>"
        "</header>"
    )


def build_header(locale: str) -> gr.HTML:
    return gr.HTML(render_header_html(locale), elem_id="main-title")
