"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, PenLine, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  ArtifactsBrowser,
  firstArtifactPath,
  type Artifact,
  type Handoff,
  type Preview,
} from "../../components/results/artifacts-browser";
import { InjectionCheckPanel } from "../../components/results/injection-check-panel";
import { getRunJson, INJECTION_TONE, type RunRow } from "../../components/results/run-api";
import { SessionRecordsPanel } from "../../components/results/session-records-panel";
import { apiFetch } from "../../lib/api";
import { filterVisibleRuns } from "../../lib/run-filters";
import { loadResultFiles, readResultFile, type ResultFile } from "./load-files";

type Manifest = {
  status?: string;
  current_stage?: string | null;
  status_reason?: string | null;
  run_id?: string | null;
};

type Results = {
  manifest: Manifest;
  handoffs: Handoff[];
  artifacts: Artifact[];
};

type DetailTab = "injection" | "sessions" | "artifacts";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function ResultsPage() {
  const router = useRouter();
  const [data, setData] = useState<Results | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [packing, setPacking] = useState(false);
  const [selected, setSelected] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [fileError, setFileError] = useState("");
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [detailTab, setDetailTab] = useState<DetailTab>("artifacts");
  const selectedRef = useRef("");
  const requestRef = useRef(0);
  const selectedRunRef = useRef("");

  const openPath = useCallback(async (filePath: string, artifacts: Artifact[]) => {
    const request = ++requestRef.current;
    selectedRef.current = filePath;
    setSelected(filePath);
    setFileError("");
    const group = artifacts.find((item) => item.path === filePath && (item.count || 1) > 1);
    if (group) {
      setPreview({ path: group.path, kind: "group", size: group.size, text: "", count: group.count || 0 });
      return;
    }
    try {
      const response = await apiFetch(`/api/results/file?path=${encodeURIComponent(filePath)}`);
      const body = (await response.json()) as ResultFile & { detail?: string };
      if (request !== requestRef.current) return;
      if (response.status === 404 && body.detail === "Not Found") {
        const file = await readResultFile(filePath);
        if (request !== requestRef.current) return;
        setPreview(file);
        return;
      }
      if (!response.ok) throw new Error(body.detail || `无法读取文件（HTTP ${response.status}）`);
      setPreview(body);
    } catch (reason: unknown) {
      if (request !== requestRef.current) return;
      setPreview(null);
      setFileError(reason instanceof Error ? reason.message : "无法读取文件");
    }
  }, []);

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setBusy(true);
    try {
      let next: Results;
      const response = await apiFetch("/api/results");
      if (response.status === 404) {
        next = await loadResultFiles();
      } else {
        const body = (await response.json()) as Results & { detail?: string };
        if (!response.ok) throw new Error(body.detail || `无法读取结果（HTTP ${response.status}）`);
        next = body;
      }
      setData(next);
      setError("");
      const current = selectedRef.current;
      const known = new Set([
        ...next.handoffs.map((h) => `workspace/records/handoffs/${h.name}`),
        ...next.artifacts.map((item) => item.path),
      ]);
      const target = current && known.has(current) ? current : firstArtifactPath(next.handoffs, next.artifacts);
      if (target && (!silent || target !== current)) void openPath(target, next.artifacts);

      const manifestRun = String(next.manifest.run_id || "").trim();
      if (!selectedRunRef.current && manifestRun) {
        selectedRunRef.current = manifestRun;
        setSelectedRunId(manifestRun);
      }
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "无法读取结果");
    } finally {
      if (!silent) setBusy(false);
    }
  }, [openPath]);

  const loadRuns = useCallback(async () => {
    try {
      const body = await getRunJson<{ runs: RunRow[] }>("/api/runs");
      const visible = filterVisibleRuns(body.runs);
      setRuns(visible);
      setSelectedRunId((cur) => {
        if (cur && visible.some((r) => r.run_id === cur)) return cur;
        const manifestRun = String(data?.manifest.run_id || "").trim();
        if (manifestRun && visible.some((r) => r.run_id === manifestRun)) return manifestRun;
        return visible[0]?.run_id || "";
      });
    } catch {
      setRuns([]);
    }
  }, [data?.manifest.run_id]);

  useEffect(() => {
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(true), 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    void loadRuns();
    const timer = setInterval(() => void loadRuns(), 8000);
    return () => clearInterval(timer);
  }, [loadRuns]);

  useEffect(() => {
    selectedRunRef.current = selectedRunId;
  }, [selectedRunId]);

  const empty = Boolean(data) && !data?.handoffs.length && !data?.artifacts.length;
  const manifestRunId = String(data?.manifest.run_id || "").trim();
  const artifactsForRun = selectedRunId && manifestRunId && selectedRunId === manifestRunId;

  async function downloadOutputs() {
    setPacking(true);
    setError("");
    try {
      let response = await apiFetch("/api/results/archive");
      if (response.status === 404) {
        const missing = (await response.json().catch(() => ({}))) as { detail?: string };
        if (missing.detail !== "Not Found") throw new Error(missing.detail || "还没有产出");
        response = await fetch("/results/archive");
      }
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail || "无法下载产出");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "lca-outputs.zip";
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "无法下载产出");
    } finally {
      setPacking(false);
    }
  }

  return (
    <div className="plan-board">
      <section className="settings-card plan-card results-card">
        <div className="section-head plan-head">
          <div className="plan-intro">
            <h2>结果与历史</h2>
          </div>
          <div className="run-meta">
            <button type="button" onClick={() => void refresh()} disabled={busy}>
              <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
              {busy ? "刷新中…" : "刷新"}
            </button>
            <button type="button" onClick={() => void downloadOutputs()} disabled={packing}>
              <Download size={16} strokeWidth={1.75} aria-hidden="true" />
              {packing ? "打包中…" : "下载产出"}
            </button>
            <button type="button" onClick={() => router.push("/plan?mode=revise")}>
              <PenLine size={16} strokeWidth={1.75} aria-hidden="true" />
              修改计划
            </button>
          </div>
        </div>
        {error ? <p className="status-banner error">{error}</p> : null}

        <nav className="results-run-history" aria-label="历史运行">
          <h3>历史运行</h3>
          {runs.length === 0 ? <p className="settings-help">还没有带会话快照的运行记录。</p> : null}
          <ul className="results-run-list">
            {runs.map((run) => (
              <li key={run.run_id}>
                <button
                  type="button"
                  className={selectedRunId === run.run_id ? "is-active" : ""}
                  aria-current={selectedRunId === run.run_id ? "true" : undefined}
                  onClick={() => setSelectedRunId(run.run_id)}
                >
                  <strong>{run.run_id}</strong>
                  <span>
                    {run.sessions} 个会话
                    {run.anomaly ? (
                      <span className={`badge badge-${INJECTION_TONE[run.level] || "warn"}`} style={{ marginLeft: 6 }}>
                        注入异常
                      </span>
                    ) : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {selectedRunId ? (
          <>
            <div className="results-detail-tabs" role="tablist" aria-label="运行详情">
              <button
                type="button"
                role="tab"
                aria-selected={detailTab === "injection"}
                className={detailTab === "injection" ? "is-active" : ""}
                onClick={() => setDetailTab("injection")}
              >
                注入核对
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={detailTab === "sessions"}
                className={detailTab === "sessions" ? "is-active" : ""}
                onClick={() => setDetailTab("sessions")}
              >
                会话记录
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={detailTab === "artifacts"}
                className={detailTab === "artifacts" ? "is-active" : ""}
                onClick={() => setDetailTab("artifacts")}
              >
                产物
              </button>
            </div>
            {detailTab === "injection" ? <InjectionCheckPanel runId={selectedRunId} /> : null}
            {detailTab === "sessions" ? <SessionRecordsPanel runId={selectedRunId} /> : null}
            {detailTab === "artifacts" ? (
              artifactsForRun ? (
                <ArtifactsBrowser
                  handoffs={data?.handoffs || []}
                  artifacts={data?.artifacts || []}
                  empty={empty}
                  selected={selected}
                  preview={preview}
                  fileError={fileError}
                  formatSize={formatSize}
                  onOpen={(path) => void openPath(path, data?.artifacts || [])}
                />
              ) : (
                <p className="settings-help" style={{ marginTop: 12 }}>
                  工作区产物只对当前一轮运行（{manifestRunId || "未知"}）保留。请选择该运行，或到 workspace/outputs 查看磁盘上的文件。
                </p>
              )
            ) : null}
          </>
        ) : (
          <p className="settings-help" style={{ marginTop: 12 }}>选择一次运行以查看注入核对、会话记录或产物。</p>
        )}
      </section>
    </div>
  );
}
