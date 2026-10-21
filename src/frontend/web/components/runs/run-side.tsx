"use client";

// 当前阶段 side panel + 失败/中断原因 popup, restored from master 599ed0a (run-side / run-stage / run-reason-panel CSS).
// v5 data: /api/v5/status (status, reason, current_node, node errors/rounds) and /api/v5/events (turn_aborted details).
import { useState } from "react";
import { AlertCircle, CircleStop } from "lucide-react";
import { ActivitySummary } from "./activity-summary";
import { label } from "../../lib/labels";
import { statusTone, type RunEvent } from "../../lib/run-events";

type NodeStatus = { id: string; status: string; round: number; error: string };
type RunStatus = { status: string; reason: string; current_node: string | null; nodes: NodeStatus[]; running: boolean };

export function failureText(run: RunStatus | null, events: RunEvent[]): string {
  if (!run) return "";
  const lines: string[] = [];
  if (run.reason) lines.push(run.reason);
  for (const n of run.nodes) if (n.error) lines.push(`${n.id}：${n.error}`);
  const aborts = events.filter((e) => e.kind === "turn_aborted" && e.detail).slice(-3);
  for (const e of aborts) lines.push(`${e.node || ""}${e.role ? ` / ${e.role}` : ""}：${String(e.detail)}`);
  return [...new Set(lines)].join("\n");
}

export function RunSide({ run, events, onStop, stopping }: {
  run: RunStatus | null; events: RunEvent[]; onStop: () => void; stopping: boolean;
}) {
  const [reasonOpen, setReasonOpen] = useState(false);
  const status = run?.status || "idle";
  const tone = statusTone(status);
  const failed = status === "failed" || status === "stopped" || status === "interrupted";
  const current = run?.nodes.find((n) => n.id === run.current_node);
  const lastNode = [...(run?.nodes || [])].reverse().find((n) => n.status !== "pending");
  const stageText = run?.current_node
    ? run.current_node
    : status === "completed"
      ? run?.reason ? `全部完成 · ${run.reason}` : "全部完成"
      : failed && lastNode
        ? `${label(status)} · 最后阶段 ${lastNode.id}`
        : status === "running" ? "准备开始" : label(status);
  const attempt = current?.round || 0;
  const reason = failureText(run, events);
  const title = status === "stopped" || status === "interrupted" ? "中断原因" : "失败原因";
  return (
    <aside className="run-side" data-testid="run-side">
      <div className={`run-stage is-${tone}`}>
        <div className="run-stage-head">
          <span>当前阶段</span>
          <span className={`badge badge-${tone}${status === "running" ? " is-live" : ""}`}>
            {status === "running" ? <span className="run-live-dot" aria-hidden="true" /> : null}
            {label(status)}
          </span>
        </div>
        <strong data-testid="run-stage-text">{stageText}</strong>
        {attempt > 0 || status === "running" || failed ? (
          <div className="run-stage-foot">
            {attempt > 0 ? <span className="run-stage-attempt">第 {attempt} 轮</span> : null}
            {status === "running" ? (
              <button type="button" className="run-stage-action" onClick={onStop} disabled={stopping}>
                <CircleStop size={12} strokeWidth={2} aria-hidden="true" />
                {stopping ? "正在中止…" : "中止工作"}
              </button>
            ) : null}
            {failed ? (
              <button type="button" className="run-stage-action" aria-expanded={reasonOpen} data-testid="run-show-reason"
                onClick={() => setReasonOpen(true)}>
                <AlertCircle size={12} strokeWidth={2} aria-hidden="true" />
                显示原因
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
      {reasonOpen ? (
        <div className="run-reason-panel" role="dialog" aria-label={title} data-testid="run-reason-panel">
          <div className="run-reason-head">
            <h3>{title}</h3>
            <button type="button" onClick={() => setReasonOpen(false)}>关闭</button>
          </div>
          <div className="run-reason-body agent-prose">
            <p style={{ whiteSpace: "pre-wrap" }}>{reason || `没有记录到这次${title.slice(0, 2)}的原因。`}</p>
          </div>
        </div>
      ) : null}
      <ActivitySummary events={events} running={status === "running"} />
    </aside>
  );
}
