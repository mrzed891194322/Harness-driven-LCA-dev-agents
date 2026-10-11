"use client";

import { useEffect, useState } from "react";
import { runStatusLabel, runStatusTone } from "../../lib/run-status";
import { apiFetch } from "../../lib/api";

type RunRow = {
  run_id: string;
  sessions?: number;
  workflow_status?: string;
  mtime?: number;
};

export function RunHistoryList({ highlightRunId = "" }: { highlightRunId?: string }) {
  const [rows, setRows] = useState<RunRow[]>([]);
  const [error, setError] = useState("");

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
          return (
            <li key={row.run_id} className={active ? "run-history-item is-active" : "run-history-item"}>
              <code title={row.run_id}>{row.run_id.slice(0, 8)}</code>
              <span className={`badge badge-${tone}`}>{runStatusLabel(status)}</span>
              {typeof row.sessions === "number" ? <small>{row.sessions} 个会话</small> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
