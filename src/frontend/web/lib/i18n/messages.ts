import zh from "../../locales/zh.json";
import en from "../../locales/en.json";

export type Locale = "zh" | "en";

export type MessageVars = Record<string, string | number>;

export const LOCALES: { id: Locale; htmlLang: string; label: string }[] = [
  { id: "zh", htmlLang: "zh-CN", label: "中文" },
  { id: "en", htmlLang: "en", label: "English" },
];

export const MESSAGES: Record<Locale, Record<string, string>> = {
  zh: zh as Record<string, string>,
  en: en as Record<string, string>,
};

function applyVars(text: string, vars?: MessageVars): string {
  if (!vars) return text;
  let out = text;
  for (const [key, value] of Object.entries(vars)) {
    out = out.split(`{${key}}`).join(String(value));
  }
  return out;
}

/** Look up a key; missing English falls back to Chinese, then the raw key. */
export function translate(locale: Locale, key: string, vars?: MessageVars): string {
  const text = MESSAGES[locale][key] ?? MESSAGES.zh[key] ?? key;
  return applyVars(text, vars);
}
