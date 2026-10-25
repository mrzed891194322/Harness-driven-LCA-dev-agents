"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiFetch } from "../api";
import { LOCALES, type Locale, type MessageVars, translate } from "./messages";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (next: Locale) => Promise<void>;
  t: (key: string, vars?: MessageVars) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);
const STORAGE_KEY = "harness.gui.lang";

function normalize(value: string | null | undefined): Locale {
  const text = (value || "").trim().toLowerCase();
  if (text.startsWith("en")) return "en";
  return "zh";
}

function htmlLang(locale: Locale): string {
  return LOCALES.find((item) => item.id === locale)?.htmlLang || "zh-CN";
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("zh");

  useEffect(() => {
    let cancelled = false;
    const cached = normalize(typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null);
    setLocaleState(cached);
    document.documentElement.lang = htmlLang(cached);
    (async () => {
      try {
        const response = await apiFetch("/api/settings/locale", { cache: "no-store" });
        if (!response.ok) return;
        const data = (await response.json()) as { lang?: string };
        if (cancelled) return;
        const next = normalize(data.lang);
        setLocaleState(next);
        window.localStorage.setItem(STORAGE_KEY, next);
        document.documentElement.lang = htmlLang(next);
      } catch {
        /* keep cached / default */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setLocale = useCallback(async (next: Locale) => {
    setLocaleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.lang = htmlLang(next);
    try {
      await apiFetch("/api/settings/locale", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lang: next }),
      });
    } catch {
      /* UI already switched; persistence can retry next visit */
    }
  }, []);

  const t = useCallback((key: string, vars?: MessageVars) => translate(locale, key, vars), [locale]);

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const value = useContext(LocaleContext);
  if (!value) throw new Error("useLocale must be used within LocaleProvider");
  return value;
}
