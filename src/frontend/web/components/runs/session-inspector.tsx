"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

type DiffItem = { item: string; level: "ok" | "warn" | "mismatch"; kind: string; critical?: boolean; [k: string]: unknown };
type SessionRow = {
  session: string;
  level: string;
  critical_mismatch: boolean;
  anomalies: DiffItem[];
  model?: { provider?: string; model_id?: string } | null;
  files: string[];
};
type RunRow = { run_id: string; sessions: number; level: string; anomaly: boolean; mismatches: Array<{ session: string; item: string }> };
type Injection = {
  intended: Record<string, any> | null;
  effective: Record<string, any> | null;
  diff: { level: string; items: DiffItem[] } | null;
  first_request: Record<string, any> | null;
};

const TONE: Record<string, string> = { ok: "ok", warn: "warn", mismatch: "fail", unknown: "off" };
const LEVEL_LABEL: Record<string, string> = { ok: "一致", warn: "提示", mismatch: "注入异常", unknown: "未知" };

async function getJson<T>(url: string): Promise<T> {
  const r = await apiFetch(url);
  const data = await r.json();
  if (!r.ok) throw new Error((data && data.detail) || `HTTP ${r.status}`);
  return data as T;
}

function fileUrl(run: string, session: string, name: string, download = false) {
  const q = new URLSearchParams({ name, ...(download ? { download: "true" } : {}) });
  return `/api/runs/${encodeURIComponent(run)}/sessions/${encodeURIComponent(session)}/file?${q}`;
}

function Pre({ text }: { text: string }) {
  return (
    <pre style={{ whiteSpace: "pre-wrap", maxHeight: 360, overflow: "auto", fontSize: 12, background: "var(--panel-2, #f6f6f6)", padding: 8 }}>
      {text}
    </pre>
  );
}

function InjectionView({ run, session }: { run: string; session: string }) {
  const [data, setData] = useState<Injection | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setData(null);
    getJson<Injection>(`/api/runs/${encodeURIComponent(run)}/sessions/${encodeURIComponent(session)}/injection`)
      .then(setData)
      .catch((e) => setError(String(e?.message || e)));
  }, [run, session]);
  if (error) return <p className="status-banner error">{error}</p>;
  if (!data) return <p>加载中…</p>;
  const it = data.intended || {};
  const ef = data.effective || {};
  const items = data.diff?.items || [];
  const rows: Array<[string, unknown, unknown]> = [
    ["模型", `${it.model?.provider}/${it.model?.model_id}`, ef.captured ? `${ef.model?.provider}/${ef.model?.model_id}` : "未采集"],
    ["system prompt 哈希", it.system_prompt_hash, ef.system_prompt_hash ?? "未采集"],
    ["工具", (it.tool_whitelist || []).join(", "), (ef.active_tool_names || []).join(", ") || "未采集"],
    ["MCP", Object.keys(it.mcp || {}).join(", "), Object.entries(ef.mcp_servers || {}).map(([k, v]: any) => `${k}(${v.tools.length}, ${v.exposures.join("/")})`).join(", ")],
    ["路径守卫钩子", "挂载", ef.captured ? (ef.guard_hook_mounted ? "已挂载" : "未挂载") : "未采集"],
    ["skills", (it.skills || []).join(", ") || "无", (ef.skills || []).join(", ") || "无"],
    ["首个模型请求", "记录", data.first_request ? (data.first_request.system_prompt_found ? "已记录，含 system prompt" : "已记录，未找到 system prompt") : "尚未发生或未采集"],
  ];
  return (
    <div>
      <table className="data-table" style={{ width: "100%", fontSize: 13 }}>
        <thead>
          <tr><th>项</th><th>计划注入（宿主）</th><th>实际生效（pi-runtime）</th></tr>
        </thead>
        <tbody>
          {rows.map(([k, a, b]) => (
            <tr key={k}><td>{k}</td><td style={{ wordBreak: "break-all" }}>{String(a ?? "")}</td><td style={{ wordBreak: "break-all" }}>{String(b ?? "")}</td></tr>
          ))}
        </tbody>
      </table>
      <h4>比对结果</h4>
      <ul style={{ fontSize: 13 }}>
        {items.map((i) => (
          <li key={i.item} style={{ color: i.level === "mismatch" ? "#c0392b" : i.level === "warn" ? "#b9770e" : undefined }}>
            [{i.level}] {i.item}：{i.kind}{i.critical ? "（关键项）" : ""}
            {i.detail ? ` — ${String(i.detail)}` : ""}
          </li>
        ))}
      </ul>
      <details>
        <summary>计划注入的 system prompt</summary>
        <Pre text={String(it.system_prompt || "")} />
      </details>
      <details>
        <summary>实际生效的 system prompt（含 SDK 追加部分）</summary>
        <Pre text={String(ef.system_prompt || ef.reason || "未采集")} />
      </details>
      {it.first_user_prompt ? (
        <details>
          <summary>首条 user 提示词</summary>
          <Pre text={String(it.first_user_prompt.text || "")} />
        </details>
      ) : null}
    </div>
  );
}

function FilesView({ run, row }: { run: string; row: SessionRow }) {
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  useEffect(() => {
    if (!name) return;
    setText("加载中…");
    getJson<{ text: string; truncated: boolean }>(fileUrl(run, row.session, name))
      .then((d) => setText(d.text + (d.truncated ? "\n…（已截断，请下载完整文件）" : "")))
      .catch((e) => setText(String(e?.message || e)));
  }, [run, row.session, name]);
  return (
    <div>
      <p style={{ fontSize: 13 }}>
        模型：{row.model?.provider}/{row.model?.model_id}
      </p>
      <ul style={{ fontSize: 13 }}>
        {row.files.map((f) => (
          <li key={f}>
            <button type="button" className="link-button" onClick={() => setName(f)}>{f}</button>{" "}
            <a href={fileUrl(run, row.session, f, true)}>下载</a>
          </li>
        ))}
      </ul>
      {name ? <Pre text={text} /> : null}
    </div>
  );
}

export function SessionInspector({ currentRunId }: { currentRunId: string }) {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [run, setRun] = useState("");
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [session, setSession] = useState("");
  const [tab, setTab] = useState<"injection" | "sessions">("injection");

  useEffect(() => {
    getJson<{ runs: RunRow[] }>("/api/runs").then((d) => {
      setRuns(d.runs);
      setRun((cur) => cur || currentRunId || d.runs[0]?.run_id || "");
    }).catch(() => setRuns([]));
  }, [currentRunId]);

  useEffect(() => {
    if (!run) return;
    getJson<{ sessions: SessionRow[] }>(`/api/runs/${encodeURIComponent(run)}/sessions`)
      .then((d) => {
        setSessions(d.sessions);
        setSession((cur) => (d.sessions.some((s) => s.session === cur) ? cur : d.sessions[0]?.session || ""));
      })
      .catch(() => setSessions([]));
  }, [run]);

  const current = runs.find((r) => r.run_id === run);
  const row = sessions.find((s) => s.session === session);
  return (
    <section className="session-inspector" style={{ marginTop: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <label>
          运行{" "}
          <select value={run} onChange={(e) => setRun(e.target.value)}>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.anomaly ? "⚠ " : ""}{r.run_id}（{r.sessions} 个会话）
              </option>
            ))}
          </select>
        </label>
        {current?.anomaly ? (
          <span className={`badge badge-${TONE[current.level] || "warn"}`}>
            注入异常：{current.mismatches.length} 项不一致
          </span>
        ) : current ? <span className="badge badge-ok">注入一致</span> : null}
        <button type="button" className={tab === "injection" ? "is-active" : ""} onClick={() => setTab("injection")}>注入</button>
        <button type="button" className={tab === "sessions" ? "is-active" : ""} onClick={() => setTab("sessions")}>会话</button>
      </div>
      <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
        <ul style={{ minWidth: 220, fontSize: 13, listStyle: "none", padding: 0 }}>
          {sessions.map((s) => (
            <li key={s.session}>
              <button type="button" className="link-button" onClick={() => setSession(s.session)}
                style={{ fontWeight: s.session === session ? 700 : 400 }}>
                <span className={`badge badge-${TONE[s.level] || "off"}`}>{LEVEL_LABEL[s.level] || s.level}</span> {s.session}
              </button>
            </li>
          ))}
        </ul>
        <div style={{ flex: 1, minWidth: 0 }}>
          {!run || !row ? <p>暂无会话快照。</p> : tab === "injection" ? <InjectionView run={run} session={row.session} /> : <FilesView run={run} row={row} />}
        </div>
      </div>
    </section>
  );
}
