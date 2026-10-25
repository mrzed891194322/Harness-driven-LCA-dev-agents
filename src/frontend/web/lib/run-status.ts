import { translate, type Locale } from "./i18n/messages";

export type RunStatusKey = "idle" | "running" | "failed" | "completed" | "interrupted" | "aborted";

export function uiLang(): Locale {
  const lang = (typeof document !== "undefined" ? document.documentElement.lang : "zh-CN").toLowerCase();
  return lang.startsWith("en") ? "en" : "zh";
}

export function runStatusLabel(status: string, lang: Locale = uiLang()): string {
  const key = `label.${status}`;
  const translated = translate(lang, key);
  return translated === key ? status : translated;
}

export function runStatusTone(status: string): "fail" | "warn" | "ok" | "off" {
  if (status === "failed" || status === "aborted") return "fail";
  if (status === "interrupted") return "warn";
  if (status === "idle") return "off";
  return "ok";
}
