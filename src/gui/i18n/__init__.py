"""GUI locale helpers."""

from __future__ import annotations

from gui.i18n.messages import MESSAGES

SUPPORTED_LOCALES = ("zh", "en")
LOCALE_DROPDOWN_CHOICES: list[tuple[str, str]] = [
    ("中文", "zh"),
    ("English", "en"),
]

RIGHT_TAB_IDS: dict[str, list[str]] = {
    "project": ["terminal_tab", "settings_init_tab"],
    "terminal": ["terminal_tab"],
    "plan": ["terminal_tab", "plan_editor_tab"],
    "running": ["terminal_tab"],
    "result": ["terminal_tab", "lca_result_tab"],
    "lciReport": ["terminal_tab", "lca_result_tab", "lci_mapping_tab"],
    "improvement": ["terminal_tab", "lca_result_tab", "lca_improvement_tab"],
}


def normalize_locale(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in ("en", "english", "en-us", "en_us"):
        return "en"
    return "zh"


def t(key: str, locale: str, **kwargs: object) -> str:
    lang = normalize_locale(locale)
    table = MESSAGES.get(lang, MESSAGES["zh"])
    template = table.get(key) or MESSAGES["zh"].get(key) or key
    if kwargs:
        return template.format(**kwargs)
    return template


def html_lang_attr(locale: str) -> str:
    return "zh-CN" if normalize_locale(locale) == "zh" else "en"
