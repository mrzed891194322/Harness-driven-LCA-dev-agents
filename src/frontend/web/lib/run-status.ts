export type RunStatusKey = "idle" | "running" | "failed" | "completed" | "interrupted" | "aborted";

export const RUN_STATUS_LABEL: Record<RunStatusKey, { zh: string; en: string }> = {
  idle: { zh: "空闲", en: "Idle" },
  running: { zh: "运行中", en: "Running" },
  failed: { zh: "失败", en: "Failed" },
  completed: { zh: "完成", en: "Completed" },
  interrupted: { zh: "已中断", en: "Interrupted" },
  aborted: { zh: "已中止", en: "Aborted" },
};

export function uiLang(): "zh" | "en" {
  const lang = (typeof document !== "undefined" ? document.documentElement.lang : "zh-CN").toLowerCase();
  return lang.startsWith("en") ? "en" : "zh";
}

export function runStatusLabel(status: string, lang: "zh" | "en" = uiLang()): string {
  const row = RUN_STATUS_LABEL[status as RunStatusKey];
  if (row) return lang === "en" ? row.en : row.zh;
  return status;
}

export function runStatusTone(status: string): "fail" | "warn" | "ok" | "off" {
  if (status === "failed" || status === "aborted") return "fail";
  if (status === "interrupted") return "warn";
  if (status === "idle") return "off";
  return "ok";
}
