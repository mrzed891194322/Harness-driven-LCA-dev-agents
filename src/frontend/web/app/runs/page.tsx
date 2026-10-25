"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, CircleStop, Play, RefreshCw, Terminal } from "lucide-react";
import { useRouter } from "next/navigation";
import { ActivitySummary } from "../../components/runs/activity-summary";
import { AgentStream, AgentProse } from "../../components/runs/agent-stream";
import { apiFetch } from "../../lib/api";
import { fetchWorkflowList } from "../../lib/workflow-manifest";
import { runStatusLabel, runStatusTone } from "../../lib/run-status";
import { itemsToActivity, itemsToLog, lastNodeFromItems, nodeLabel, type RunItem } from "../../lib/run-items";
import { useLocale } from "../../lib/i18n/locale-context";

type Progress = {
  run_id?: string | null;
  status?: string;
  current_node?: string | null;
  attempt?: number | null;
  status_reason?: string | null;
  model?: string | null;
  rev?: number | null;
  items?: RunItem[];
  next_seq?: number;
  reset?: boolean;
  workflow?: string | null;
};

export default function RunsPage() {
  const { t } = useLocale();
  const router = useRouter();
  const [progress, setProgress] = useState<Progress>({ status: "idle" });
  const [runItems, setRunItems] = useState<RunItem[]>([]);
  const [error, setError] = useState("");
  const [reasonOpen, setReasonOpen] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [activityAttempt, setActivityAttempt] = useState(0);
  const afterSeq = useRef(0);
  const runId = useRef("");

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
          after_seq: String(afterSeq.current),
          run_id: runId.current,
        });
        const response = await apiFetch(`/api/workflow/progress?${query.toString()}`);
        const data = (await response.json()) as Progress & { detail?: string };
        if (!response.ok) throw new Error(data.detail || t("runs.readFailHttp", { status: response.status }));
        if (cancelled) return;
        const nextRun = String(data.run_id || "");
        const fresh = data.items || [];
        const switched = Boolean(runId.current) && nextRun !== runId.current;
        if (data.reset || switched) setRunItems(fresh);
        else if (fresh.length) setRunItems((current) => current.concat(fresh));
        afterSeq.current = Number(data.next_seq) || 0;
        runId.current = nextRun;
        setProgress(data);
        setError("");
      } catch (reason: unknown) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : t("runs.readFail"));
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
  }, [t]);

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
    const mainWorkflow = list.find((item) => item.mode === "main") ?? list[0];
    const mainTitle = mainWorkflow?.title ?? t("runs.current");
    const taskId = mainWorkflow?.id ?? "";
    if (!taskId) {
      setError(t("runs.noTaskId"));
      return;
    }
    const ok = confirm(t("runs.confirmRestart", { title: mainTitle }));
    if (!ok) return;
    setRestarting(true);
    setError("");
    try {
      const planResponse = await apiFetch("/api/plan");
      const plan = (await planResponse.json()) as {
        fields?: Record<string, string>;
        detail?: string;
      };
      if (!planResponse.ok) throw new Error(plan.detail || t("runs.planFailHttp", { status: planResponse.status }));
      const fields = plan.fields || {};
      const response = await apiFetch("/api/workflow/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow: taskId,
          subject: fields.subject || "",
          functional_unit: fields.functional_unit || "",
          life_cycle_stages: fields.life_cycle_stages || "",
          conditions: fields.conditions || "",
        }),
      });
      const data = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(data.detail || t("runs.startFailHttp", { status: response.status }));
      afterSeq.current = 0;
      runId.current = "";
      setRunItems([]);
      router.refresh();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : t("runs.restartFail"));
    } finally {
      setRestarting(false);
    }
  }

  async function resumeRun() {
    setResuming(true);
    setError("");
    try {
      const response = await apiFetch("/api/workflow/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow: progress.workflow }),
      });
      const data = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(data.detail || t("runs.resumeFailHttp", { status: response.status }));
      setReasonOpen(false);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : t("runs.resumeFail"));
    } finally {
      setResuming(false);
    }
  }

  async function stopWork() {
    setStopping(true);
    setError("");
    try {
      const response = await apiFetch("/api/workflow/stop", { method: "POST" });
      const data = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(data.detail || t("runs.stopFailHttp", { status: response.status }));
    } catch (reason: unknown) {
      setStopping(false);
      setError(reason instanceof Error ? reason.message : t("runs.stopFail"));
    }
  }

  const model = (progress.model || "").trim();
  const log = useMemo(() => itemsToLog(runItems, model), [runItems, model]);
  const activity = useMemo(() => itemsToActivity(runItems), [runItems]);
  const lastNode = useMemo(() => lastNodeFromItems("", runItems), [runItems]);
  const current = (progress.current_node || "").trim();
  const currentLabel = useMemo(() => {
    const last = [...runItems].reverse().find((item) => item.node === current);
    return last ? nodeLabel(current, last.redo || 0) : current;
  }, [runItems, current]);

  const nodeText = (() => {
    if (current) return currentLabel;
    if (status === "completed") return reason ? t("runs.allDoneWith", { reason }) : t("runs.allDone");
    if (status === "failed" || status === "interrupted" || status === "aborted") {
      return lastNode ? t("runs.lastStage", { label, node: lastNode }) : label;
    }
    if (status === "running") return t("runs.ready");
    return progress.run_id ? label : t("runs.ready");
  })();

  return (
    <div className="plan-board">
      <section className="settings-card plan-card run-card">
        <div className="section-head plan-head">
          <div className="plan-intro">
            <h2>
              <Terminal className="plan-title-icon" size={20} strokeWidth={1.75} aria-hidden="true" />
              {t("runs.terminal")}
            </h2>
          </div>
        </div>
        {error ? <p className="status-banner error" data-testid="run-error">{error}</p> : null}
        <div className="run-body">
          <div className="run-terminal">
            <AgentStream text={log} running={status === "running"} model={model} />
            {reasonOpen ? (
              <div className="run-reason-panel" data-testid="run-reason-panel" role="dialog" aria-label={status === "interrupted" ? t("runs.interruptReason") : t("runs.failReason")}>
                <div className="run-reason-head">
                  <h3>{status === "interrupted" ? t("runs.interruptReason") : t("runs.failReason")}</h3>
                  <button type="button" onClick={() => setReasonOpen(false)}>
                    {t("common.close")}
                  </button>
                </div>
                <div className="run-reason-body agent-prose">
                  {reason ? (
                    <AgentProse text={reason} />
                  ) : (
                    <p>{status === "interrupted" ? t("runs.noInterruptReason") : t("runs.noFailReason")}</p>
                  )}
                </div>
                <div className="run-reason-foot">
                  <button
                    type="button"
                    data-testid="run-resume"
                    disabled={resuming || !progress.workflow}
                    title={t("runs.resumeTitle")}
                    onClick={() => void resumeRun()}
                  >
                    <RefreshCw size={14} strokeWidth={1.75} aria-hidden="true" />
                    {t("runs.rerunRound")}
                  </button>
                </div>
              </div>
            ) : null}
          </div>
          <aside className="run-side" data-testid="run-side">
            <div className={`run-node is-${tone}`}>
              <div className="run-node-head">
<span>{t("runs.currentStage")}</span>
                <span className={`badge badge-${tone}${status === "running" ? " is-live" : ""}`} data-testid="run-status" data-status={status}>
                  {status === "running" ? <span className="run-live-dot" aria-hidden="true" /> : null}
                  {label}
                </span>
              </div>
              <strong data-testid="run-node-text">{nodeText}</strong>
              {attempt > 0 || status === "running" || status === "failed" || status === "interrupted" ? (
                <div className="run-node-foot">
                  {attempt > 0 ? <span className="run-node-attempt">{t("runs.attempt", { n: attempt })}</span> : null}
                  {status === "running" ? (
                    <button
                      type="button"
                      className="run-node-action"
                      data-testid="run-stop"
                      onClick={() => void stopWork()}
                      disabled={stopping}
                    >
                      <CircleStop size={12} strokeWidth={2} aria-hidden="true" />
                      {stopping ? t("runs.stopping") : t("runs.stop")}
                    </button>
                  ) : null}
                  {status === "failed" || status === "interrupted" ? (
                    <button
                      type="button"
                      className="run-node-action"
                      aria-expanded={reasonOpen}
                      data-testid="run-show-reason"
                      onClick={() => setReasonOpen(true)}
                    >
                      <AlertCircle size={12} strokeWidth={2} aria-hidden="true" />
                      {t("runs.showReason")}
                    </button>
                  ) : null}
                  {status === "interrupted" ? (
                    <button
                      type="button"
                      className="run-node-action"
                      data-testid="run-restart"
                      onClick={() => void restartFromScratch()}
                      disabled={restarting}
                    >
                      <Play size={12} strokeWidth={2} aria-hidden="true" />
                      {restarting ? t("runs.starting") : t("runs.restart")}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
            <ActivitySummary
              runId={String(progress.run_id || "")}
              events={activity}
              running={status === "running"}
              currentNode={currentLabel}
              onNodeAttempt={setActivityAttempt}
            />
          </aside>
        </div>
      </section>
    </div>
  );
}
