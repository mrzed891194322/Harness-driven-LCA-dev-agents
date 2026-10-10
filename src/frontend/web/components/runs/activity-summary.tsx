"use client";

import { useEffect, useRef, useState } from "react";
import { History, Play } from "lucide-react";
import { apiFetch } from "../../lib/api";

/** One record of /api/workflow/activity (events.jsonl written by the Pi client). */
export type ActivityEvent = {
  run_id?: string;
  stage?: string;
  role?: string;
  assignment?: string;
  attempt?: number;
  kind?: "tool_call" | "tool_result" | "text" | "turn_end";
  tool?: string;
  tool_call_id?: string;
  summary?: string;
  is_error?: boolean;
  handoff?: boolean;
  ts?: string;
};

type Handoff = "none" | "pending" | "ok" | "err";

export type AssignmentActivity = {
  key: string;
  stage: string;
  role: string;
  attempt: number;
  tools: number;
  errors: number;
  running: string;
  lastTool: string;
  lastDetail: string;
  handoff: Handoff;
  handoffNote: string;
  turnEnded: boolean;
};

const ROLE_LABEL: Record<string, string> = {
  reviewer: "审查",
  executor: "执行",
  reviser: "修订",
};

const HANDOFF_LABEL: Record<Handoff, string> = {
  none: "未交卷",
  pending: "交卷中",
  ok: "已交卷",
  err: "交卷失败",
};

export function summarizeActivity(events: ActivityEvent[]): AssignmentActivity[] {
  const byKey = new Map<string, AssignmentActivity>();
  const open = new Map<string, Set<string>>();
  for (const event of events) {
    const stage = event.stage || "";
    const role = event.role || "";
    const key = event.assignment || `${stage}.${role}`;
    let entry = byKey.get(key);
    if (!entry) {
      entry = {
        key,
        stage,
        role,
        attempt: 0,
        tools: 0,
        errors: 0,
        running: "",
        lastTool: "",
        lastDetail: "",
        handoff: "none",
        handoffNote: "",
        turnEnded: false,
      };
      byKey.set(key, entry);
      open.set(key, new Set());
    }
    const attempt = Number(event.attempt) || 0;
    if (attempt > entry.attempt) {
      entry.attempt = attempt;
      if (entry.handoff !== "ok") entry.handoff = "none";
    }
    const pending = open.get(key)!;
    const tool = event.tool || "";
    const callId = event.tool_call_id || tool;
    if (event.kind === "tool_call") {
      entry.turnEnded = false;
      entry.tools += 1;
      entry.lastTool = tool;
      entry.lastDetail = event.summary || "";
      pending.add(callId);
      entry.running = tool;
      if (event.handoff) entry.handoff = "pending";
    } else if (event.kind === "tool_result") {
      pending.delete(callId);
      entry.running = pending.size ? entry.running : "";
      if (event.is_error) {
        entry.errors += 1;
        entry.lastDetail = event.summary || entry.lastDetail;
      }
      if (event.handoff) {
        entry.handoff = event.is_error ? "err" : "ok";
        entry.handoffNote = event.summary || "";
      }
    } else if (event.kind === "turn_end") {
      pending.clear();
      entry.running = "";
      entry.turnEnded = true;
      if (event.is_error) entry.errors += 1;
    }
  }
  return [...byKey.values()];
}

export function ActivitySummary({ runId, running = false }: { runId: string; running?: boolean }) {
  const [items, setItems] = useState<AssignmentActivity[]>([]);
  const events = useRef<ActivityEvent[]>([]);
  const offset = useRef(0);
  const current = useRef("");

  useEffect(() => {
    let cancelled = false;
    let busy = false;
    if (current.current !== runId) {
      current.current = runId;
      events.current = [];
      offset.current = 0;
      setItems([]);
    }
    if (!runId) return;

    async function tick() {
      if (busy) return;
      busy = true;
      try {
        const query = new URLSearchParams({ run_id: runId, offset: String(offset.current) });
        const response = await apiFetch(`/api/workflow/activity?${query.toString()}`);
        if (!response.ok) return;
        const data = (await response.json()) as {
          events?: ActivityEvent[];
          offset?: number;
          reset?: boolean;
        };
        if (cancelled) return;
        if (data.reset) events.current = [];
        const fresh = data.events || [];
        offset.current = Number(data.offset) || 0;
        if (fresh.length || data.reset) {
          events.current = events.current.concat(fresh);
          setItems(summarizeActivity(events.current));
        }
      } catch {
        // The main progress feed already reports backend errors.
      } finally {
        busy = false;
      }
    }

    void tick();
    const timer = setInterval(() => void tick(), 1500);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [runId]);

  if (!items.length) return null;
  return (
    <ul className="activity-summary" aria-label="各分工活动概览">
      {items.map((item) => {
        const role = ROLE_LABEL[item.role] || item.role;
        const tone =
          item.handoff === "ok"
            ? "ok"
            : item.handoff === "err"
              ? "fail"
              : item.turnEnded
                ? "warn"
                : "off";
        const note = item.handoff === "err" ? item.handoffNote : "";
        const active =
          running &&
          Boolean(item.stage) &&
          (Boolean(item.running) ||
            item.handoff === "pending" ||
            (!item.turnEnded && item.handoff === "none"));
        return (
          <li
            key={item.key}
            className={active ? "activity-chip is-live" : "activity-chip"}
            title={note || item.lastDetail || undefined}
          >
            <span className="activity-chip-head">
              <span className="activity-chip-mark" role="img" aria-label={active ? "正在执行" : "历史记录"}>
                {active ? <Play size={13} strokeWidth={1.75} /> : <History size={13} strokeWidth={1.75} />}
              </span>
              <strong>{item.stage}</strong>
              <small>
                {role}
                {item.attempt ? ` · 第 ${item.attempt} 次` : ""}
              </small>
            </span>
            <span className="activity-chip-body">
              <span>
                {item.tools} 次工具调用
                {item.errors ? <em className="activity-chip-err"> · {item.errors} 个错误</em> : null}
              </span>
              {item.running ? (
                <span className="activity-chip-running">
                  <span className="agent-spinner" aria-hidden="true" />
                  {item.running}
                </span>
              ) : null}
              <span className={`badge badge-${tone}`}>{HANDOFF_LABEL[item.handoff]}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
