/** One label map for run/node states and review verdicts (used by /runs, its events panel and /results). */
export const LABEL: Record<string, string> = {
  idle: "空闲",
  running: "运行中",
  pending: "等待",
  completed: "完成",
  passed: "通过",
  failed: "失败",
  stopped: "已停止",
  error: "错误",
  blocked: "受阻",
  ok: "完成",
  pass: "通过",
  accept: "通过",
  fail: "退回",
  reject: "退回",
};

export function label(value: string | undefined | null): string {
  return value ? LABEL[value] || value : "";
}
