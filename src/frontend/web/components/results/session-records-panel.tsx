"use client";

import { useEffect, useState } from "react";
import { SessionSidebar } from "./session-sidebar";
import { getRunJson, sessionFileUrl, type SessionRow } from "./run-api";

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

function SessionFiles({ runId, row }: { runId: string; row: SessionRow }) {
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  useEffect(() => {
    if (!name) return;
    setText("加载中…");
    if (name === "__markdown__") {
      getRunJson<{ text: string }>(
        `/api/runs/${encodeURIComponent(runId)}/sessions/${encodeURIComponent(row.session)}/markdown`,
      )
        .then((d) => setText(d.text))
        .catch((e) => setText(String(e?.message || e)));
      return;
    }
    getRunJson<{ text: string; truncated: boolean }>(sessionFileUrl(runId, row.session, name))
      .then((d) => setText(d.text + (d.truncated ? "\n…（已截断，请下载完整文件）" : "")))
      .catch((e) => setText(String(e?.message || e)));
  }, [runId, row.session, name]);
  return (
    <div>
      <p style={{ fontSize: 13 }}>
        模型：{row.model?.provider}/{row.model?.model_id}
      </p>
      <p style={{ fontSize: 13 }}>
        <button type="button" onClick={() => setName("__markdown__")}>查看完整对话（Markdown）</button>{" "}
        <a
          href={`/api/runs/${encodeURIComponent(runId)}/sessions/${encodeURIComponent(row.session)}/markdown?download=true`}
        >
          下载 Markdown
        </a>
      </p>
      <ul style={{ fontSize: 13 }}>
        {row.files.map((f) => (
          <li key={f}>
            <button type="button" className="link-button" onClick={() => setName(f)}>{f}</button>{" "}
            <a href={sessionFileUrl(runId, row.session, f, true)}>下载</a>
          </li>
        ))}
      </ul>
      {name ? <Pre text={text} /> : null}
    </div>
  );
}

export function SessionRecordsPanel({ runId }: { runId: string }) {
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
      {!row ? <p>暂无会话快照。</p> : <SessionFiles runId={runId} row={row} />}
    </SessionSidebar>
  );
}
