"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, PenLine, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { MarkdownView } from "../../components/markdown-view";
import { apiFetch } from "../../lib/api";
import { loadResultFiles, readResultFile, type ResultFile } from "./load-files";

type Manifest = {
  status?: string;
  current_stage?: string | null;
  status_reason?: string | null;
  run_id?: string | null;
};

type Handoff = {
  name: string;
  stage: string;
  role: string;
  attempt: number | null;
  status: string;
  status_reason: string;
  artifacts: string[];
};

type Artifact = {
  path: string;
  size: number;
  count?: number;
};

type Results = {
  manifest: Manifest;
  handoffs: Handoff[];
  artifacts: Artifact[];
};

type Preview =
  | ResultFile
  | { path: string; kind: "group"; size: number; text: ""; count: number };

const HANDOFF_STATUS: Record<string, string> = {
  ok: "完成",
  failed: "失败",
  blocked: "受阻",
  passed: "通过",
};

const ROLE_LABEL: Record<string, string> = {
  executor: "执行",
  reviser: "修订",
  reviewer: "审查",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function handoffPath(item: Handoff): string {
  return `workspace/records/handoffs/${item.name}`;
}

function baseName(filePath: string): string {
  const parts = filePath.split("/");
  return parts[parts.length - 1] || filePath;
}

function navTitle(item: Artifact): string {
  if ((item.count || 1) > 1) {
    const parts = item.path.split("/");
    return parts.slice(-2).join("/");
  }
  return baseName(item.path);
}

function parentName(filePath: string): string {
  const trimmed = filePath
    .replace(/^workspace\/outputs\//, "")
    .replace(/^workspace\/records\/handoffs\//, "");
  const slash = trimmed.lastIndexOf("/");
  return slash >= 0 ? trimmed.slice(0, slash) : "";
}

function firstPath(data: Results): string {
  if (data.handoffs[0]) return handoffPath(data.handoffs[0]);
  return data.artifacts[0]?.path || "";
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
  const selectedRef = useRef("");
  const requestRef = useRef(0);

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
        ...next.handoffs.map(handoffPath),
        ...next.artifacts.map((item) => item.path),
      ]);
      const target = current && known.has(current) ? current : firstPath(next);
      if (target && (!silent || target !== current)) void openPath(target, next.artifacts);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "无法读取结果");
    } finally {
      if (!silent) setBusy(false);
    }
  }, [openPath]);

  useEffect(() => {
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(true), 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  const empty = Boolean(data) && !data?.handoffs.length && !data?.artifacts.length;

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
        <div className="results-columns">
          <nav className="results-pane results-nav" aria-label="文件">
            {empty ? <p className="settings-help">还没有文件。</p> : null}
            {data?.handoffs.length ? (
              <section>
                <h3>工作记录</h3>
                <ul>
                  {data.handoffs.map((item) => {
                    const filePath = handoffPath(item);
                    return (
                      <li key={filePath}>
                        <button
                          type="button"
                          aria-current={selected === filePath ? "page" : undefined}
                          onClick={() => void openPath(filePath, data.artifacts)}
                        >
                          <strong>{item.stage || item.name}</strong>
                          <span>
                            {ROLE_LABEL[item.role] || item.role || "交接"}
                            {item.attempt != null ? ` · 第 ${item.attempt} 次` : ""}
                            {item.status ? ` · ${HANDOFF_STATUS[item.status] || item.status}` : ""}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ) : null}
            {data?.artifacts.length ? (
              <section>
                <h3>产物</h3>
                <ul>
                  {data.artifacts.map((item) => (
                    <li key={item.path}>
                      <button
                        type="button"
                        aria-current={selected === item.path ? "page" : undefined}
                        onClick={() => void openPath(item.path, data.artifacts)}
                      >
                        <strong>{navTitle(item)}</strong>
                        <span>
                          {item.count && item.count > 1
                            ? `${item.count} 个中间文件`
                            : parentName(item.path) || formatSize(item.size)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </nav>
          <section className="results-pane results-view" aria-label="文件内容">
            {preview ? (
              <>
                <header className="results-view-head">
                  <strong className="results-path">{preview.path}</strong>
                  {preview.kind !== "group" ? <span>{formatSize(preview.size)}</span> : null}
                </header>
                <div className="results-view-body">
                  {preview.kind === "group" ? (
                    <p className="settings-help">
                      这是中间调用记录，共 {preview.count} 个文件，{formatSize(preview.size)}。
                    </p>
                  ) : preview.kind === "too-large" ? (
                    <p className="settings-help">文件较大（{formatSize(preview.size)}），这里不展开。</p>
                  ) : preview.kind === "markdown" ? (
                    <MarkdownView source={preview.text} />
                  ) : preview.text ? (
                    <pre className="results-source">
                      <code>{preview.text}</code>
                    </pre>
                  ) : (
                    <p className="settings-help">文件是空的。</p>
                  )}
                </div>
              </>
            ) : (
              <p className="settings-help">{fileError || "选择左侧文件查看内容。"}</p>
            )}
          </section>
        </div>
      </section>
    </div>
  );
}
