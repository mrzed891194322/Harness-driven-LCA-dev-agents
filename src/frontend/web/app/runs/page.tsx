"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle, CircleStop, Play, RefreshCw, Terminal } from "lucide-react";
import { useRouter } from "next/navigation";
import { ActivitySummary } from "../../components/runs/activity-summary";
import { AgentStream, AgentProse } from "../../components/runs/agent-stream";
import { apiFetch } from "../../lib/api";
import { fetchWorkflowList, workflowListItemForMode } from "../../lib/workflow-manifest";
import { runStatusLabel, runStatusTone } from "../../lib/run-status";
import { lastStageFromEvents, type ActivityEvent } from "../../lib/run-activity";

type Progress = {
  run_id?: string | null;
  status?: string;
  current_stage?: string | null;
  attempt?: number | null;
  status_reason?: string | null;
  model?: string | null;
  text?: string;
  offset?: number;
  reset?: boolean;
  epoch?: string;
};

export default function RunsPage() {
  const router = useRouter();
  const [progress, setProgress] = useState<Progress>({ status: "idle", text: "" });
  const [log, setLog] = useState("");
  const [error, setError] = useState("");
  const [reasonOpen, setReasonOpen] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [lastStage, setLastStage] = useState("");
  const [activityAttempt, setActivityAttempt] = useState(0);
  const offset = useRef(0);
  const runId = useRef("");
  const epoch = useRef("");
  const activityOffset = useRef(0);

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
  const label = runStatusLabel(status);
  const tone = runStatusTone(status);
  const reason = (progress.status_reason || "").trim();
  const attempt = Number(progress.attempt) || activityAttempt;

  useEffect(() => {
    if (status !== "failed" && status !== "interrupted") setReasonOpen(false);
    if (status !== "running") setStopping(false);
  }, [status]);

  async function restartFromScratch() {
    const list = await fetchWorkflowList().catch(() => []);
    const mainWorkflow = workflowListItemForMode(list, "new") ?? list[0];
    const mainTitle = mainWorkflow?.title ?? "当前";
    const taskId = mainWorkflow?.id ?? "";
    if (!taskId) {
      setError("无法读取工作流任务 id");
      return;
    }
    const ok = confirm(`确定要从头重跑吗？将按当前计划重新执行「${mainTitle}」工作流。`);
    if (!ok) return;
    setRestarting(true);
    setError("");
    try {
      const planResponse = await apiFetch("/api/plan");
      const plan = (await planResponse.json()) as {
        fields?: Record<string, string>;
        detail?: string;
      };
      if (!planResponse.ok) throw new Error(plan.detail || `无法读取计划（HTTP ${planResponse.status}）`);
      const fields = plan.fields || {};
      const response = await apiFetch("/api/workflow/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: taskId,
          subject: fields.subject || "",
          functional_unit: fields.functional_unit || "",
          life_cycle_stages: fields.life_cycle_stages || "",
          conditions: fields.conditions || "",
        }),
      });
      const data = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(data.detail || `无法启动（HTTP ${response.status}）`);
      offset.current = 0;
      epoch.current = "";
      runId.current = "";
      setLog("");
      router.refresh();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "无法从头重跑");
    } finally {
      setRestarting(false);
    }
  }

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

  useEffect(() => {
    const run = String(progress.run_id || "");
    if (!run) {
      setLastStage("");
      activityOffset.current = 0;
      return;
    }
    let cancelled = false;
    async function check() {
      try {
        const query = new URLSearchParams({
          run_id: run,
          offset: String(activityOffset.current),
        });
        const response = await apiFetch(`/api/workflow/activity?${query.toString()}`);
        if (!response.ok || cancelled) return;
        const data = (await response.json()) as {
          events?: ActivityEvent[];
          offset?: number;
          reset?: boolean;
        };
        if (data.reset) activityOffset.current = 0;
        activityOffset.current = Number(data.offset) || activityOffset.current;
        const events = data.events || [];
        if (cancelled) return;
        if (data.reset) {
          setLastStage(lastStageFromEvents("", events));
        } else {
          setLastStage((current) => lastStageFromEvents(current, events));
        }
      } catch {
        // ignore
      }
    }
    void check();
    const timer = setInterval(() => void check(), 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [progress.run_id]);

  const stageText = (() => {
    const current = (progress.current_stage || "").trim();
    if (current) return current;
    if (status === "completed") return reason ? `全部完成 · ${reason}` : "全部完成";
    if (status === "failed" || status === "interrupted" || status === "aborted") {
      return lastStage ? `${label} · 最后阶段 ${lastStage}` : label;
    }
    if (status === "running") return "准备开始";
    return progress.run_id ? label : "准备开始";
  })();

  return (
    <div className="plan-board">
      <section className="settings-card plan-card run-card">
        <div className="section-head plan-head">
          <div className="plan-intro">
            <h2>
              <Terminal className="plan-title-icon" size={20} strokeWidth={1.75} aria-hidden="true" />
              实时终端
            </h2>
          </div>
        </div>
        {error ? <p className="status-banner error">{error}</p> : null}
        <div className="run-body">
          <div className="run-terminal">
            <AgentStream text={log} running={status === "running"} model={(progress.model || "").trim()} />
            {reasonOpen ? (
              <div className="run-reason-panel" role="dialog" aria-label={status === "interrupted" ? "中断原因" : "失败原因"}>
                <div className="run-reason-head">
                  <h3>{status === "interrupted" ? "中断原因" : "失败原因"}</h3>
                  <button type="button" onClick={() => setReasonOpen(false)}>
                    关闭
                  </button>
                </div>
                <div className="run-reason-body agent-prose">
                  {reason ? (
                    <AgentProse text={reason} />
                  ) : (
                    <p>{status === "interrupted" ? "没有记录到这次中断的原因。" : "没有记录到这次失败的原因。"}</p>
                  )}
                </div>
                <div className="run-reason-foot">
                  <button type="button" disabled title="计划从检查点续跑本阶段，尚未接入">
                    <RefreshCw size={14} strokeWidth={1.75} aria-hidden="true" />
                    重跑本轮
                  </button>
                </div>
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
              <strong>{stageText}</strong>
              {attempt > 0 || status === "running" || status === "failed" || status === "interrupted" ? (
                <div className="run-stage-foot">
                  {attempt > 0 ? <span className="run-stage-attempt">第 {attempt} 次</span> : null}
                  {status === "running" ? (
                    <button
                      type="button"
                      className="run-stage-action"
                      onClick={() => void stopWork()}
                      disabled={stopping}
                    >
                      <CircleStop size={12} strokeWidth={2} aria-hidden="true" />
                      {stopping ? "正在中止…" : "中止工作"}
                    </button>
                  ) : null}
                  {status === "failed" || status === "interrupted" ? (
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
                  {status === "interrupted" ? (
                    <button
                      type="button"
                      className="run-stage-action"
                      onClick={() => void restartFromScratch()}
                      disabled={restarting}
                    >
                      <Play size={12} strokeWidth={2} aria-hidden="true" />
                      {restarting ? "正在启动…" : "从头重跑"}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
            <ActivitySummary
              runId={String(progress.run_id || "")}
              running={status === "running"}
              currentStage={String(progress.current_stage || "")}
              onStageAttempt={setActivityAttempt}
            />
          </aside>
        </div>
      </section>
    </div>
  );
}
