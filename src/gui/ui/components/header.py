"""顶部标题栏：标题、项目链接与作者信息。

需要改标题栏文字或链接时只改本文件顶部常量；样式在 ``ui/assets/css/header.css``。
"""

from html import escape

import gradio as gr

HEADER_TITLE = "🌲 生命周期评估多智能体系统 - 控制面板"
GITHUB_URL = "https://github.com/mrzed891194322/Harness-driven-LCA-dev-agents"
GITHUB_LABEL = "GitHub"
AUTHOR_NAME = "Du Yuan"
AUTHOR_EMAIL = "yuandu0214@outlook.com"


def render_header_html(
    *,
    title: str = HEADER_TITLE,
    github_url: str = GITHUB_URL,
    github_label: str = GITHUB_LABEL,
    author_name: str = AUTHOR_NAME,
    author_email: str = AUTHOR_EMAIL,
) -> str:
    link_attrs = 'target="_blank" rel="noopener noreferrer"'
    return (
        '<header class="app-header">'
        f'<h1 class="app-header-title">{escape(title)}</h1>'
        '<div class="app-header-meta">'
        f'<a class="app-header-link" href="{escape(github_url)}" {link_attrs}>'
        f"{escape(github_label)}</a>"
        '<span class="app-header-sep" aria-hidden="true">·</span>'
        f'<span class="app-header-author">作者：{escape(author_name)}</span>'
        '<span class="app-header-sep" aria-hidden="true">·</span>'
        f'<a class="app-header-link" href="mailto:{escape(author_email)}">'
        f"{escape(author_email)}</a>"
        "</div>"
        "</header>"
    )


def build_header() -> gr.HTML:
    return gr.HTML(render_header_html(), elem_id="main-title")
