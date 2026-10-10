"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle, CircleStop } from "lucide-react";
import { ActivitySummary } from "../../components/runs/activity-summary";
import { AgentStream } from "../../components/runs/agent-stream";
import { apiFetch } from "../../lib/api";

type Progress = {
  run_id?: string | null;
  status?: string;
  current_stage?: string | null;
  status_reason?: string | null;
  model?: string | null;
  text?: string;
  offset?: number;
  reset?: boolean;
  epoch?: string;
};

const STATUS_LABEL: Record<string, string> = {
  idle: "空闲",
  running: "运行中",
  failed: "失败",
  completed: "完成",
};

export default function RunsPage() {
  const [progress, setProgress] = useState<Progress>({ status: "idle", text: "" });
  const [log, setLog] = useState("");
  const [error, setError] = useState("");
  const [reasonOpen, setReasonOpen] = useState(false);
  const [stopping, setStopping] = useState(false);
  const offset = useRef(0);
  const runId = useRef("");
  const epoch = useRef("");

  useEffect(() => {
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  useEffect(() => {
    let cancelled = false;
    let busy = false;

    async function tick() {
      if (busy) return;
      busy = true;
      try {
        const query = new URLSearchParams({
          offset: String(offset.current),
          epoch: epoch.current,
        });
        const response = await apiFetch(`/api/workflow/progress?${query.toString()}`);
        const data = (await response.json()) as Progress & { detail?: string };
        if (!response.ok) throw new Error(data.detail || `无法读取运行输出（HTTP ${response.status}）`);
        if (cancelled) return;
        const nextRun = String(data.run_id || "");
        const chunk = data.text || "";
        const switched = Boolean(runId.current) && nextRun !== runId.current;
        if (data.reset || switched) setLog(chunk);
        else if (chunk) setLog((current) => current + chunk);
        offset.current = Number(data.offset) || 0;
        epoch.current = data.epoch || "";
        runId.current = nextRun;
        setProgress(data);
        setError("");
      } catch (reason: unknown) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "无法读取运行输出");
      } finally {
        busy = false;
      }
    }

    void tick();
    const timer = setInterval(() => void tick(), 800);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const status = progress.status || "idle";
  const label = STATUS_LABEL[status] || status;
  const tone = status === "failed" ? "fail" : status === "idle" ? "off" : "ok";
  const reason = (progress.status_reason || "").trim();

  useEffect(() => {
    if (status !== "failed") setReasonOpen(false);
    if (status !== "running") setStopping(false);
  }, [status]);

  async function stopWork() {
    setStopping(true);
    setError("");
    try {
      const response = await apiFetch("/api/workflow/stop", { method: "POST" });
      const data = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(data.detail || `无法中止工作（HTTP ${response.status}）`);
    } catch (reason: unknown) {
      setStopping(false);
      setError(reason instanceof Error ? reason.message : "无法中止工作");
    }
  }

  return (
    <div className="plan-board">
      <section className="settings-card plan-card run-card">
        <div className="section-head plan-head">
          <div className="plan-intro">
            <h2>实时终端</h2>
          </div>
        </div>
        {error ? <p className="status-banner error">{error}</p> : null}
        <div className="run-body">
          <div className="run-terminal">
            <AgentStream text={log} running={status === "running"} model={(progress.model || "").trim()} />
            {reasonOpen ? (
              <div className="run-reason-panel" role="dialog" aria-label="失败原因">
                <div className="run-reason-head">
                  <h3>失败原因</h3>
                  <button type="button" onClick={() => setReasonOpen(false)}>
                    关闭
                  </button>
                </div>
                <pre>{reason || "没有记录到这次失败的原因。"}</pre>
              </div>
            ) : null}
          </div>
          <aside className="run-side">
            <div className={`run-stage is-${tone}`}>
              <div className="run-stage-head">
                <span>当前阶段</span>
                <span className={`badge badge-${tone}${status === "running" ? " is-live" : ""}`}>
                  {status === "running" ? <span className="run-live-dot" aria-hidden="true" /> : null}
                  {label}
                </span>
              </div>
              <strong>{progress.current_stage || "尚未开始"}</strong>
              {status === "running" ? (
                <button
                  type="button"
                  className="run-stage-action danger"
                  onClick={() => void stopWork()}
                  disabled={stopping}
                >
                  <CircleStop size={12} strokeWidth={2} aria-hidden="true" />
                  {stopping ? "正在中止…" : "中止工作"}
                </button>
              ) : null}
              {status === "failed" ? (
                <button
                  type="button"
                  className="run-stage-action"
                  aria-expanded={reasonOpen}
                  onClick={() => setReasonOpen(true)}
                >
                  <AlertCircle size={12} strokeWidth={2} aria-hidden="true" />
                  显示原因
                </button>
              ) : null}
            </div>
            <ActivitySummary runId={String(progress.run_id || "")} />
          </aside>
        </div>
      </section>
    </div>
  );
}
