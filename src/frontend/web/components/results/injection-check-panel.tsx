"use client";

import { useEffect, useState } from "react";
import { SessionSidebar } from "./session-sidebar";
import {
  getRunJson,
  type Injection,
  type SessionRow,
} from "./run-api";

function Pre({ text }: { text: string }) {
  return (
    <pre
      style={{
        whiteSpace: "pre-wrap",
        maxHeight: 360,
        overflow: "auto",
        fontSize: 12,
        background: "var(--panel-2, #f6f6f6)",
        padding: 8,
      }}
    >
      {text}
    </pre>
  );
}

function InjectionDetail({ runId, session }: { runId: string; session: string }) {
  const [data, setData] = useState<Injection | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setData(null);
    getRunJson<Injection>(
      `/api/runs/${encodeURIComponent(runId)}/sessions/${encodeURIComponent(session)}/injection`,
    )
      .then(setData)
      .catch((e) => setError(String(e?.message || e)));
  }, [runId, session]);
  if (error) return <p className="status-banner error">{error}</p>;
  if (!data) return <p>加载中…</p>;
  const it = data.intended || {};
  const ef = data.effective || {};
  const items = data.diff?.items || [];
  const rows: Array<[string, unknown, unknown]> = [
    ["模型", `${it.model?.provider}/${it.model?.model_id}`, ef.captured ? `${ef.model?.provider}/${ef.model?.model_id}` : "未采集"],
    ["system prompt 哈希", it.system_prompt_hash, ef.system_prompt_hash ?? "未采集"],
    ["工具", (it.tool_whitelist || []).join(", "), (ef.active_tool_names || []).join(", ") || "未采集"],
    [
      "MCP",
      Object.keys(it.mcp || {}).join(", "),
      Object.entries(ef.mcp_servers || {})
        .map(([k, v]: [string, any]) => `${k}(${v.tools.length}, ${v.exposures.join("/")})`)
        .join(", "),
    ],
    ["路径守卫钩子", "挂载", ef.captured ? (ef.guard_hook_mounted ? "已挂载" : "未挂载") : "未采集"],
    ["skills", (it.skills || []).join(", ") || "无", (ef.skills || []).join(", ") || "无"],
    [
      "首个模型请求",
      "记录",
      data.first_request
        ? data.first_request.system_prompt_found
          ? "已记录，含 system prompt"
          : "已记录，未找到 system prompt"
        : "尚未发生或未采集",
    ],
  ];
  return (
    <div>
      <table className="data-table" style={{ width: "100%", fontSize: 13 }}>
        <thead>
          <tr>
            <th>项</th>
            <th>计划注入（宿主）</th>
            <th>实际生效（pi-runtime）</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([k, a, b]) => (
            <tr key={k}>
              <td>
                {k}
                {k === "system prompt 哈希" ? (
                  <p className="settings-help" style={{ margin: "4px 0 0", fontWeight: 400 }}>
                    Pi SDK 会在实际请求中追加运行协议等内容（effective 侧常见 sdk_added），因此哈希与计划值不一致通常属于预期差异，不代表注入失败。
                  </p>
                ) : null}
              </td>
              <td style={{ wordBreak: "break-all" }}>{String(a ?? "")}</td>
              <td style={{ wordBreak: "break-all" }}>{String(b ?? "")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>比对结果</h4>
      <ul style={{ fontSize: 13 }}>
        {items.map((i) => (
          <li
            key={i.item}
            style={{ color: i.level === "mismatch" ? "#c0392b" : i.level === "warn" ? "#b9770e" : undefined }}
          >
            [{i.level}] {i.item}：{i.kind}
            {i.critical ? "（关键项）" : ""}
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

export function InjectionCheckPanel({ runId }: { runId: string }) {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [session, setSession] = useState("");

  useEffect(() => {
    if (!runId) return;
    getRunJson<{ sessions: SessionRow[] }>(`/api/runs/${encodeURIComponent(runId)}/sessions`)
      .then((d) => {
        setSessions(d.sessions);
        setSession((cur) => (d.sessions.some((s) => s.session === cur) ? cur : d.sessions[0]?.session || ""));
      })
      .catch(() => {
        setSessions([]);
        setSession("");
      });
  }, [runId]);

  const row = sessions.find((s) => s.session === session);
  return (
    <SessionSidebar sessions={sessions} session={session} onSelect={setSession}>
      {!row ? <p>暂无会话快照。</p> : <InjectionDetail runId={runId} session={row.session} />}
    </SessionSidebar>
  );
}
