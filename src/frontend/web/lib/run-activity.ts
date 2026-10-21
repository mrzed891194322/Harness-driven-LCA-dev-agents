import type { RunEvent } from "./run-events.ts";

/**
 * Per node.role.round activity chips (old 599ed0a ActivitySummary), rebuilt from /api/v5/events.
 * v5 has no per-tool events, so the chip counts model retries / rejections / nudges instead of tool calls.
 */
export type Handoff = "none" | "pending" | "ok" | "err";
export type AssignmentActivity = {
  key: string;
  stage: string;
  role: string;
  attempt: number;
  retries: number;
  rejections: number;
  nudges: number;
  handoff: Handoff;
  note: string;
  turnEnded: boolean;
  verdict: string;
};

export const HANDOFF_LABEL: Record<Handoff, string> = { none: "未交卷", pending: "进行中", ok: "已交卷", err: "交卷失败" };

export function summarizeActivity(events: RunEvent[]): AssignmentActivity[] {
  const byKey = new Map<string, AssignmentActivity>();
  const lastKey = new Map<string, string>(); // node.role -> key of its latest round
  for (const e of events) {
    const stage = e.node || "";
    if (!stage) continue;
    if (e.kind === "review_verdict") {
      const k = lastKey.get(`${stage}.reviewer`);
      if (k) byKey.get(k)!.verdict = String(e.verdict || "");
      continue;
    }
    const role = e.role || "";
    if (!role) continue;
    const attempt = Number(e.round) || 0;
    const key = `${stage}.${role}#${attempt}`;
    let entry = byKey.get(key);
    if (!entry) {
      entry = { key, stage, role, attempt, retries: 0, rejections: 0, nudges: 0, handoff: "none", note: "", turnEnded: false, verdict: "" };
      byKey.set(key, entry);
      lastKey.set(`${stage}.${role}`, key);
    }
    switch (e.kind) {
      case "turn_start":
        entry.turnEnded = false;
        entry.handoff = "pending";
        break;
      case "model_retry":
        entry.retries += 1;
        entry.note = String(e.detail || "");
        break;
      case "submit_rejected":
      case "rejected_retry":
        if (e.kind === "submit_rejected") entry.rejections += 1;
        break;
      case "nudge":
        entry.nudges += 1;
        break;
      case "turn_aborted":
        entry.note = String(e.detail || e.reason || "");
        break;
      case "agent_settled":
        entry.turnEnded = true;
        if (e.submitted === true || e.submitted === "True") entry.handoff = "ok";
        else {
          entry.handoff = "err";
          entry.note = String(e.error || e.abort_reason || entry.note || "");
        }
        break;
    }
  }
  return [...byKey.values()];
}

export function isLive(item: AssignmentActivity, running: boolean): boolean {
  return running && item.handoff === "pending" && !item.turnEnded;
}
