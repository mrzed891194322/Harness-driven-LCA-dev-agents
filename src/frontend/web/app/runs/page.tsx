"use client";

import { useEffect, useRef, useState } from "react";
import { ActivitySummary } from "../../components/runs/activity-summary";
import { AgentStream } from "../../components/runs/agent-stream";

type Progress = {
  run_id?: string | null;
  status?: string;
  current_stage?: string | null;
  status_reason?: string | null;
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
        const response = await fetch(`/api/workflow/progress?${query.toString()}`);
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

  return (
    <div className="plan-board">
      <section className="settings-card plan-card run-card">
        <div className="section-head plan-head">
          <div className="plan-intro">
            <h2>运行详情</h2>
          </div>
          <div className="run-meta">
            <span className={`badge badge-${tone}`}>{label}</span>
            {progress.current_stage ? <span>{progress.current_stage}</span> : null}
          </div>
        </div>
        {reason ? (
          <p className={`run-reason${status === "failed" ? " is-fail" : ""}`} title={reason}>
            {reason}
          </p>
        ) : null}
        {error ? <p className="status-banner error">{error}</p> : null}
        <ActivitySummary runId={String(progress.run_id || "")} />
        <AgentStream text={log} running={status === "running"} />
      </section>
    </div>
  );
}
