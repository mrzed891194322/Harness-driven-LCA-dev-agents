"use client";

import { useState } from "react";
import { Check, Languages } from "lucide-react";
import { LOCALES, type Locale } from "../lib/i18n/messages";
import { useLocale } from "../lib/i18n/locale-context";

export function LanguageButton() {
  const [open, setOpen] = useState(false);
  const { locale, setLocale, t } = useLocale();

  return (
    <div
      className="language-menu"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <button
        type="button"
        className="settings-launch"
        aria-label={t("chrome.language")}
        title={t("chrome.language")}
        aria-haspopup="menu"
        aria-expanded={open}
        data-active={open ? "true" : undefined}
      >
        <Languages size={16} aria-hidden="true" className="launch-icon" />
        <span>{t("chrome.language")}</span>
      </button>
      <div className="language-menu-panel" hidden={!open}>
        <ul className="language-menu-list" role="menu" aria-label={t("chrome.languages")}>
          {LOCALES.map((language) => {
            const selected = language.id === locale;
            return (
              <li key={language.id} role="none">
                <button
                  type="button"
                  role="menuitemradio"
                  aria-checked={selected}
                  className="language-menu-item"
                  onClick={() => {
                    void setLocale(language.id as Locale);
                    setOpen(false);
                  }}
                >
                  <span>{language.label}</span>
                  {selected ? <Check size={14} aria-hidden="true" /> : null}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
