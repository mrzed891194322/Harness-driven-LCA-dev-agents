"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, FolderOpen, PenLine, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  ArtifactsBrowser,
  firstArtifactPath,
  type Artifact,
  type Handoff,
  type Preview,
} from "../../components/results/artifacts-browser";
import { apiFetch } from "../../lib/api";
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
  records?: Artifact[];
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function knownPaths(data: Results): Set<string> {
  return new Set([
    ...data.handoffs.map((item) => `workspace/records/handoffs/${item.name}`),
    ...data.artifacts.map((item) => item.path),
    ...(data.records || []).map((item) => item.path),
  ]);
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
  const previewCacheRef = useRef<Map<string, Preview>>(new Map());

  const openPath = useCallback(
    async (filePath: string, artifacts: Artifact[], signal?: AbortSignal) => {
      const request = ++requestRef.current;
      selectedRef.current = filePath;
      setSelected(filePath);
      setFileError("");
      const cached = previewCacheRef.current.get(filePath);
      if (cached) {
        setPreview(cached);
        return;
      }
      const group = artifacts.find((item) => item.path === filePath && (item.count || 1) > 1);
      if (group) {
        const entry: Preview = {
          path: group.path,
          kind: "group",
          size: group.size,
          text: "",
          count: group.count || 0,
        };
        previewCacheRef.current.set(filePath, entry);
        setPreview(entry);
        return;
      }
      try {
        const response = await apiFetch(`/api/results/file?path=${encodeURIComponent(filePath)}`, {
          signal,
        });
        const body = (await response.json()) as ResultFile & { detail?: string };
        if (signal?.aborted || request !== requestRef.current) return;
        if (response.status === 404 && body.detail === "Not Found") {
          const file = await readResultFile(filePath);
          if (signal?.aborted || request !== requestRef.current) return;
          previewCacheRef.current.set(filePath, file);
          setPreview(file);
          return;
        }
        if (!response.ok) throw new Error(body.detail || `无法读取文件（HTTP ${response.status}）`);
        previewCacheRef.current.set(filePath, body);
        setPreview(body);
      } catch (reason: unknown) {
        if (signal?.aborted || request !== requestRef.current) return;
        setPreview(null);
        setFileError(reason instanceof Error ? reason.message : "无法读取文件");
      }
    },
    [],
  );

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
      const known = knownPaths(next);
      const target = current && known.has(current)
        ? current
        : firstArtifactPath(next.handoffs, next.artifacts, next.records || []);
      if (target && target !== current) {
        void openPath(target, next.artifacts);
      }
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

  const records = data?.records || [];
  const empty = Boolean(data) && !data?.handoffs.length && !data?.artifacts.length && !records.length;

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
            <h2>
              <FolderOpen className="plan-title-icon" size={20} strokeWidth={1.75} aria-hidden="true" />
              运行结果
            </h2>
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
        <ArtifactsBrowser
          handoffs={data?.handoffs || []}
          artifacts={data?.artifacts || []}
          records={records}
          empty={empty}
          selected={selected}
          preview={preview}
          fileError={fileError}
          formatSize={formatSize}
          onOpen={(path) => void openPath(path, data?.artifacts || [])}
        />
      </section>
    </div>
  );
}
