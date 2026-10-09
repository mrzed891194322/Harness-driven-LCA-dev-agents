"use client";

import { useState } from "react";
import { Check, Languages } from "lucide-react";

const LANGUAGES = [{ id: "zh-CN", label: "中文" }] as const;

export function LanguageButton() {
  const [open, setOpen] = useState(false);
  const current = LANGUAGES[0].id;

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
        aria-label="语言"
        title="语言"
        aria-haspopup="menu"
        aria-expanded={open}
        data-active={open ? "true" : undefined}
      >
        <Languages size={16} aria-hidden="true" className="launch-icon" />
        <span>语言</span>
      </button>
      <div className="language-menu-panel" hidden={!open}>
        <ul className="language-menu-list" role="menu" aria-label="可用语言">
          {LANGUAGES.map((language) => {
            const selected = language.id === current;
            return (
              <li key={language.id} role="none">
                <button
                  type="button"
                  role="menuitemradio"
                  aria-checked={selected}
                  className="language-menu-item"
                  onClick={() => setOpen(false)}
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
