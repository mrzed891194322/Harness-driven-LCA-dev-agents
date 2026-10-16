"use client";

import { useCallback, useEffect, useState } from "react";
import { runStatusLabel, runStatusTone } from "../../lib/run-status";
import { apiFetch } from "../../lib/api";
import {
  fetchWorkflowManifest,
  resumableStageIds,
  stageTitle,
  type WorkflowManifest,
} from "../../lib/workflow-manifest";
type RunRow = {
  run_id: string;
  sessions?: number;
  workflow_status?: string;
  mtime?: number;
};

type ResumePreview = {
  eligible?: boolean;
  reasons?: string[];
  inherited_stages?: string[];
  from_stage?: string;
  reused_attempts?: { stage: string; executor?: string; reviewer?: string }[];
  cleanup?: { workspace_paths?: string[]; openlca_ids?: { type: string; id: string }[] };
  rework_note?: string;
};

const RESUMABLE = new Set(["failed", "aborted", "interrupted"]);

export function RunHistoryList({ highlightRunId = "" }: { highlightRunId?: string }) {
  const [rows, setRows] = useState<RunRow[]>([]);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [manifest, setManifest] = useState<WorkflowManifest | null>(null);
  const resumeStages = resumableStageIds(manifest);
  const [fromStage, setFromStage] = useState<string>("02-inventory-extraction");
  const [preview, setPreview] = useState<ResumePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [resuming, setResuming] = useState(false);

  useEffect(() => {
    fetchWorkflowManifest("LCA-main")
      .then((data) => {
        setManifest(data);
        const resumable = resumableStageIds(data);
        if (resumable.length) setFromStage(resumable[0]);
      })
      .catch(() => setManifest(null));
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await apiFetch("/api/runs");
        const data = (await response.json()) as { runs?: RunRow[]; detail?: string };
        if (!response.ok) throw new Error(data.detail || `无法读取运行历史（HTTP ${response.status}）`);
        if (!cancelled) {
          setRows(data.runs || []);
          setError("");
        }
      } catch (reason: unknown) {
        if (!cancelled) {
          setRows([]);
          setError(reason instanceof Error ? reason.message : "无法读取运行历史");
        }
      }
    }
    void load();
    const timer = setInterval(() => void load(), 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const selected = rows.find((r) => r.run_id === selectedId);
  const canResume = selected && RESUMABLE.has(selected.workflow_status || "");

  const loadPreview = useCallback(async (runId: string, stage: string) => {
    setPreviewLoading(true);
    try {
      const q = new URLSearchParams({ from_stage: stage });
      const response = await apiFetch(`/api/runs/${runId}/resume-preview?${q.toString()}`);
      const data = (await response.json()) as ResumePreview & { detail?: unknown };
      if (!response.ok) {
        const detail = data.detail;
        setPreview({
          eligible: false,
          reasons: Array.isArray(detail)
            ? detail.map(String)
            : typeof detail === "object" && detail && "reasons" in (detail as object)
              ? ((detail as { reasons?: string[] }).reasons || [String(detail)])
              : [String(detail || response.status)],
        });
      } else {
        setPreview(data);
      }
    } catch (reason: unknown) {
      setPreview({
        eligible: false,
        reasons: [reason instanceof Error ? reason.message : "无法加载续跑预览"],
      });
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedId || !canResume) {
      setPreview(null);
      return;
    }
    void loadPreview(selectedId, fromStage);
  }, [selectedId, fromStage, canResume, loadPreview]);

  async function confirmResume() {
    if (!selectedId) return;
    setResuming(true);
    try {
      const response = await apiFetch("/api/workflow/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: selectedId, from_stage: fromStage }),
      });
      const data = (await response.json()) as { detail?: { reasons?: string[] } | string };
      if (!response.ok) {
        const reasons =
          typeof data.detail === "object" && data.detail && "reasons" in data.detail
            ? (data.detail.reasons || []).join("；")
            : String(data.detail || response.status);
        throw new Error(reasons);
      }
      setDialogOpen(false);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "续跑启动失败");
    } finally {
      setResuming(false);
    }
  }

  if (!rows.length && !error) return null;

  return (
    <section className="run-history" aria-label="运行历史">
      <h3>运行历史</h3>
      {error ? <p className="settings-help">{error}</p> : null}
      <ul className="run-history-list">
        {rows.map((row) => {
          const status = row.workflow_status || "unknown";
          const tone = runStatusTone(status);
          const active = highlightRunId && row.run_id === highlightRunId;
          const picked = row.run_id === selectedId;
          return (
            <li key={row.run_id} className={active ? "run-history-item is-active" : "run-history-item"}>
              <button
                type="button"
                className={picked ? "run-history-select is-picked" : "run-history-select"}
                onClick={() => setSelectedId(row.run_id)}
              >
                <code title={row.run_id}>{row.run_id.slice(0, 8)}</code>
                <span className={`badge badge-${tone}`}>{runStatusLabel(status)}</span>
                {typeof row.sessions === "number" ? <small>{row.sessions} 个会话</small> : null}
              </button>
            </li>
          );
        })}
      </ul>

      {canResume ? (
        <div className="run-resume-panel">
          <p className="settings-help">选择从哪一阶段重新执行（之前阶段将沿用）。</p>
          <div className="run-resume-stages">
            {resumeStages.map((code) => (
              <label key={code}>
                <input
                  type="radio"
                  name="resume-stage"
                  value={code}
                  checked={fromStage === code}
                  onChange={() => setFromStage(code)}
                />
                {stageTitle(manifest, code)}
              </label>
            ))}
          </div>
          {preview?.inherited_stages?.length ? (
            <div className="run-resume-inherited">
              {(preview.inherited_stages || []).map((sid) => (
                <span key={sid} className="badge badge-ok" data-testid="stage-inherited">
                  {stageTitle(manifest, sid)} 沿用
                </span>
              ))}
            </div>
          ) : null}
          <button
            type="button"
            data-testid="resume-from-stage-button"
            disabled={previewLoading}
            onClick={() => setDialogOpen(true)}
          >
            从此阶段继续
          </button>
        </div>
      ) : null}

      {dialogOpen ? (
        <div className="run-reason-panel" role="dialog" data-testid="resume-confirm-dialog" aria-modal="true">
          <div className="run-reason-head">
            <h3>确认从此阶段继续</h3>
            <button type="button" data-testid="resume-cancel" onClick={() => setDialogOpen(false)}>
              取消
            </button>
          </div>
          <div className="run-reason-body">
            <p>
              起始阶段：<strong data-testid="resume-start-stage">{fromStage}</strong>
            </p>
            {preview?.rework_note ? <p className="settings-help">{preview.rework_note}</p> : null}
            {!preview?.eligible && (preview?.reasons?.length ?? 0) > 0 ? (
              <ul data-testid="resume-reasons">
                {(preview?.reasons || []).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
            <p>将复用以下已接受尝试（workspace 与 openLCA 均保留）：</p>
            <ul data-testid="resume-delete-list">
              {(preview?.reused_attempts || []).map((item) => (
                <li key={item.stage} data-testid="resume-delete-item">
                  {stageTitle(manifest, item.stage)}
                  {item.executor ? ` · 执行 ${item.executor}` : ""}
                  {item.reviewer ? ` · 审查 ${item.reviewer}` : ""}
                </li>
              ))}
            </ul>
            <ul data-testid="resume-openlca-list" hidden aria-hidden="true" />
          </div>
          <div className="run-reason-foot">
            <button
              type="button"
              data-testid="resume-confirm"
              disabled={!preview?.eligible || resuming}
              onClick={() => void confirmResume()}
            >
              {resuming ? "正在启动…" : "确认续跑"}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
