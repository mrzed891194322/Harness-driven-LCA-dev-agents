import { label as stateLabel } from "./labels.ts";

/** Event rows from /api/v5/events, and how /runs shows them. */
export type RunEvent = { ts?: string; kind: string; node?: string; role?: string; round?: number; [key: string]: unknown };

/** Kinds shown by default: control events (nudges, rejections, stops, aborts) plus node/run milestones. */
export const NOTABLE: Record<string, string> = {
  run_start: "运行开始",
  run_end: "运行结束",
  node_start: "节点开始",
  node_end: "节点结束",
  node_skip: "跳过（已通过）",
  requires_failed: "缺少输入",
  review_verdict: "审核结论",
  nudge: "催交",
  rejected_retry: "提交被拒，重试",
  submit_rejected: "提交被拒",
  too_many_rejections: "被拒次数过多",
  no_submit: "未提交",
  turn_aborted: "回合中止",
  stop_requested: "请求停止",
  stop_cancel_failed: "停止未能中断回合",
  model_preflight: "模型预检",
};

const BAD = new Set(["requires_failed", "too_many_rejections", "no_submit", "turn_aborted", "stop_cancel_failed"]);
const WARN = new Set(["nudge", "rejected_retry", "submit_rejected", "stop_requested"]);

export function eventTone(e: RunEvent): "ok" | "warn" | "fail" | "off" {
  if (BAD.has(e.kind)) return "fail";
  if (WARN.has(e.kind)) return "warn";
  if (e.kind === "model_preflight") return e.ok === false ? "fail" : "ok";
  if (e.kind === "review_verdict") return e.verdict === "reject" || e.verdict === "fail" ? "warn" : "ok";
  if (e.kind === "node_end" || e.kind === "run_end") {
    const s = String(e.status || "");
    return s === "failed" ? "fail" : s === "stopped" ? "warn" : "ok";
  }
  return "off";
}

export function isNotable(e: RunEvent): boolean {
  return e.kind in NOTABLE;
}

/** One-line description: label plus the most useful detail field. */
export function describeEvent(e: RunEvent): string {
  const label = NOTABLE[e.kind] || e.kind;
  const where = [e.node, e.role, e.round ? `第 ${e.round} 轮` : ""].filter(Boolean).join(" · ");
  const state = [e.verdict, e.status].find((v) => typeof v === "string" && v) as string | undefined;
  const text = [e.reason, e.error, e.detail, e.message].find((v) => typeof v === "string" && v)?.toString().slice(0, 200);
  const detail = [state ? stateLabel(state) : "", text].filter(Boolean).join("：");
  return [label, where, detail].filter(Boolean).join(" — ");
}

/** Merge a polled page into the list. If the log shrank (a new run reset it), start over. */
export function mergeEvents(
  prev: RunEvent[],
  prevOffset: number,
  page: { events: RunEvent[]; offset: number },
  keep = 500,
): { events: RunEvent[]; offset: number; reset: boolean } {
  if (page.offset < prevOffset) return { events: [], offset: 0, reset: true };
  return { events: [...prev, ...page.events].slice(-keep), offset: page.offset, reset: false };
}

export function statusTone(status: string): "ok" | "warn" | "fail" | "off" {
  if (status === "passed" || status === "completed") return "ok";
  if (status === "failed" || status === "error") return "fail";
  if (status === "running" || status === "stopped") return "warn";
  return "off";
}
