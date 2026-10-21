"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "../../lib/api";
import { LABEL } from "../../lib/labels";
import { initialWorkflow } from "../../lib/initial-workflow";
import { modelChoices, type ModelRow } from "../../lib/model-options";
import { describeEvent, eventTone, isNotable, mergeEvents, statusTone, type RunEvent } from "../../lib/run-events";

type AgentCard = {
  role: string;
  model: string;
  thinking: string;
  tools: { mcp: string[]; skills: string[] };
  rules: string[];
  read: string[];
  write: string[];
};
type NodeCard = {
  id: string;
  title: string;
  requires: string[];
  produces: { spec: string; path: string }[];
  max_rounds: number;
  agents: Record<string, AgentCard>;
};
type Workflow = { id: string; nodes: string[]; details: NodeCard[] };
type NodeStatus = { id: string; status: string; round: number; error: string; feedback_rounds: number[] };
type RunStatus = {
  status: string;
  reason: string;
  run_id: string;
  workflow: string;
  current_node: string | null;
  nodes: NodeStatus[];
  running: boolean;
};

const STATUS_LABEL = LABEL;

async function readJson<T>(response: Response): Promise<T> {
  const data = (await response.json()) as T & { detail?: unknown };
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return data;
}

export function V5RunPanel() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selected, setSelected] = useState("full-lca");
  const [run, setRun] = useState<RunStatus | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ node: string; round: number; text: string } | null>(null);
  const [models, setModels] = useState<ModelRow[]>([]);
  const [model, setModel] = useState("");
  const [modelNote, setModelNote] = useState("");
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [allEvents, setAllEvents] = useState(false);
  const [detail, setDetail] = useState<string | null>(null);
  const eventOffset = useRef(0);

  useEffect(() => {
    apiFetch("/api/workflow/models")
      .then((r) => readJson<{ default_ref?: string; default?: string; models: ModelRow[]; warnings?: string[] }>(r))
      .then((data) => {
        setModels(data.models || []);
        setModel(data.default_ref || data.default || "");
        if (data.warnings?.length) setModelNote(data.warnings.join("；"));
      })
      .catch((e: unknown) => setModelNote(e instanceof Error ? e.message : String(e)));
  }, []);

  async function chooseModel(value: string) {
    const previous = model;
    setModel(value);
    setModelNote("");
    try {
      await readJson(
        await apiFetch("/api/models/selection", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile_id: value }),
        }),
      );
      setModelNote("已保存，下次运行生效");
    } catch (e: unknown) {
      setModel(previous);
      setModelNote(e instanceof Error ? e.message : String(e));
    }
  }

  // After a refresh, show the current/latest run's workflow instead of the default (until the user picks one).
  const picked = useRef(false);
  const runWorkflow = useRef<string | undefined>(undefined);
  const workflowIds = useRef<string[]>([]);
  const syncSelect = useCallback(() => {
    if (!picked.current) setSelected(
        initialWorkflow(
          runWorkflow.current,
          workflowIds.current,
          "full-lca",
          new URLSearchParams(window.location.search).get("workflow") || undefined,
        ),
      );
  }, []);

  useEffect(() => {
    apiFetch("/api/v5/workflows")
      .then((r) => readJson<{ workflows: Workflow[] }>(r))
      .then((data) => {
        setWorkflows(data.workflows);
        workflowIds.current = data.workflows.map((w) => w.id);
        syncSelect();
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [syncSelect]);

  const refresh = useCallback(async () => {
    try {
      const next = await readJson<RunStatus>(await apiFetch("/api/v5/status", { cache: "no-store" }));
      setRun(next);
      if (runWorkflow.current === undefined) {
        runWorkflow.current = next.workflow || "";
        syncSelect();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [syncSelect]);

  const pollEvents = useCallback(async () => {
    try {
      const page = await readJson<{ events: RunEvent[]; offset: number }>(
        await apiFetch(`/api/v5/events?offset=${eventOffset.current}`, { cache: "no-store" }),
      );
      let merged = mergeEvents([], eventOffset.current, page);
      if (merged.reset) {
        const full = await readJson<{ events: RunEvent[]; offset: number }>(
          await apiFetch("/api/v5/events?offset=0", { cache: "no-store" }),
        );
        merged = mergeEvents([], 0, full);
        eventOffset.current = merged.offset;
        setEvents(merged.events);
        return;
      }
      eventOffset.current = page.offset;
      if (page.events.length) setEvents((prev) => [...prev, ...page.events].slice(-500));
    } catch {
      // events are best-effort; status polling reports errors
    }
  }, []);

  useEffect(() => {
    void refresh();
    void pollEvents();
    const timer = setInterval(() => {
      void refresh();
      void pollEvents();
    }, 2000);
    return () => clearInterval(timer);
  }, [refresh, pollEvents]);

  async function act(kind: "start" | "stop" | "resume") {
    setBusy(true);
    setError("");
    try {
      if (kind === "start") {
        const plan = await readJson<{ fields?: Record<string, string> }>(await apiFetch("/api/plan"));
        const f = plan.fields || {};
        await readJson(
          await apiFetch("/api/workflow/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              workflow: selected,
              subject: f.subject || "",
              functional_unit: f.functional_unit || "",
              life_cycle_stages: f.life_cycle_stages || "",
              conditions: f.conditions || "",
            }),
          }),
        );
      } else if (kind === "stop") {
        await readJson(await apiFetch("/api/workflow/stop", { method: "POST" }));
      } else {
        await readJson(
          await apiFetch("/api/v5/resume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ workflow: run?.workflow || selected }),
          }),
        );
      }
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function showFeedback(node: string, round: number) {
    try {
      const data = await readJson<{ text: string }>(await apiFetch(`/api/v5/nodes/${node}/feedback/${round}`));
      setFeedback({ node, round, text: data.text });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const wf = workflows.find((w) => w.id === selected);
  const status = run?.status || "idle";
  const rows: NodeStatus[] =
    run && run.nodes.length && (!wf || run.workflow === selected)
      ? run.nodes
      : (wf?.nodes || []).map((id) => ({ id, status: "pending", round: 0, error: "", feedback_rounds: [] }));
  const cards = new Map((wf?.details || []).map((n) => [n.id, n]));

  const shown = (allEvents ? events : events.filter(isNotable)).slice(-200).reverse();
  const detailCard = detail ? cards.get(detail) : undefined;
  const detailRow = detail ? rows.find((r) => r.id === detail) : undefined;
  const detailEvents = detail ? events.filter((e) => e.node === detail && isNotable(e)).slice(-50).reverse() : [];

  return (
    <div className="plan-board">
      <section className="settings-card plan-card v5-run-panel">
        <div className="section-head plan-head">
          <div className="plan-intro">
            <h2>运行详情</h2>
            <p className="settings-meta">
              状态：
              <span className={`badge badge-${statusTone(status)}`} data-testid="run-status" data-status={status}>
                {STATUS_LABEL[status] || status}
              </span>
              {run?.reason ? <span data-testid="run-reason">（{run.reason}）</span> : null}
              {run?.run_id ? ` · ${run.run_id.slice(0, 8)}` : ""}
              {run?.current_node ? ` · 当前节点 ${run.current_node}` : ""}
            </p>
          </div>
          <div className="run-meta">
            <button data-testid="run-start" type="button" onClick={() => void act("start")} disabled={busy || run?.running}>
              开始运行
            </button>
            <button data-testid="run-stop" type="button" onClick={() => void act("stop")} disabled={busy || !run?.running}>
              停止
            </button>
            <button data-testid="run-resume" type="button" onClick={() => void act("resume")} disabled={busy || run?.running || !run?.run_id}>
              续跑
            </button>
          </div>
        </div>
        <div className="row plan-actions">
          <label>
            工作流{" "}
            <select data-testid="workflow-select" value={selected} onChange={(e) => {
              picked.current = true;
              setSelected(e.target.value);
            }} disabled={run?.running}>
              {workflows.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.id}（{w.nodes.join(" → ")}）
                </option>
              ))}
            </select>
          </label>
          <label>
            模型{" "}
            <select
              data-testid="model-select"
              value={modelChoices(models, model).value}
              onChange={(e) => void chooseModel(e.target.value)}
              disabled={run?.running}
            >
              {modelChoices(models, model).choices.map((c) => (
                <option key={c.value || "none"} value={c.value} disabled={!c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        {modelNote ? <p className="settings-help" data-testid="model-note">提示：{modelNote}</p> : null}
        {error ? (
          <p className="status-banner error" data-testid="run-error" role="alert">
            {error}
          </p>
        ) : null}
        <div className="agent-table">
          <table data-testid="node-table">
            <thead>
              <tr>
                <th>节点</th>
                <th>状态</th>
                <th>轮次</th>
                <th>反馈</th>
                <th>错误</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((node) => (
                <tr key={node.id} data-testid={`node-row-${node.id}`} data-status={node.status}>
                  <td>
                    <button type="button" data-testid={`node-open-${node.id}`} aria-pressed={detail === node.id}
                      onClick={() => setDetail(detail === node.id ? null : node.id)}>
                      {node.id}
                      {cards.get(node.id)?.title ? ` · ${cards.get(node.id)?.title}` : ""}
                    </button>
                  </td>
                  <td>
                    <span className={`badge badge-${statusTone(node.status)}`}>{STATUS_LABEL[node.status] || node.status}</span>
                  </td>
                  <td>{node.round || ""}</td>
                  <td>
                    {node.feedback_rounds.map((r) => (
                      <button key={r} type="button" data-testid={`node-feedback-${node.id}-${r}`} onClick={() => void showFeedback(node.id, r)}>
                        第 {r} 轮
                      </button>
                    ))}
                  </td>
                  <td data-testid={`node-error-${node.id}`}>{node.error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {feedback ? (
          <section className="settings-card" data-testid="feedback-view">
            <h3>
              {feedback.node} 第 {feedback.round} 轮反馈
            </h3>
            <pre className="results-source"><code>{feedback.text}</code></pre>
          </section>
        ) : null}
        {detail ? (
          <section className="settings-card" data-testid={`node-detail-${detail}`}>
            <h3>
              {detail}
              {detailCard?.title ? ` · ${detailCard.title}` : ""}{" "}
              <span className={`badge badge-${statusTone(detailRow?.status || "pending")}`}>
                {STATUS_LABEL[detailRow?.status || "pending"] || detailRow?.status}
              </span>
            </h3>
            {detailCard ? (
              <>
                <p className="settings-help">
                  交付：{detailCard.produces.map((p) => `${p.spec} → artifacts/${p.path}`).join("，") || "无"}
                  {detailCard.requires.length ? `；需要：${detailCard.requires.join("，")}` : ""}；最多 {detailCard.max_rounds} 轮
                </p>
                <div className="agent-table">
                  <table>
                    <thead>
                      <tr><th>代理</th><th>模型</th><th>工具</th><th>规则</th><th>可写</th><th>可读</th></tr>
                    </thead>
                    <tbody>
                      {Object.entries(detailCard.agents).map(([name, a]) => (
                        <tr key={name} data-testid={`agent-card-${detail}-${name}`}>
                          <td>{name}（{a.role}）</td>
                          <td>{a.model} / 思考 {a.thinking}</td>
                          <td>文件工具{a.tools.mcp.length ? `、MCP ${a.tools.mcp.join("、")}` : ""}{a.tools.skills.length ? `、技能 ${a.tools.skills.join("、")}` : ""}</td>
                          <td>{a.rules.length ? a.rules.join("、") : "仅全局规则"}</td>
                          <td>{a.write.join("、")}</td>
                          <td>{a.read.join("、")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
            {detailRow?.error ? <p className="status-banner error">{detailRow.error}</p> : null}
            <ul className="diag-list" data-testid={`node-events-${detail}`}>
              {detailEvents.length ? detailEvents.map((e, i) => (
                <li key={i}>
                  <span className={`badge badge-${eventTone(e)}`}>{e.ts?.slice(11, 19) || ""}</span>
                  {describeEvent(e)}
                </li>
              )) : <li className="settings-meta">这个节点还没有事件。</li>}
            </ul>
          </section>
        ) : null}
        <section className="settings-card" data-testid="events-panel">
          <div className="section-head">
            <h3>事件</h3>
            <label className="settings-meta">
              <input type="checkbox" checked={allEvents} onChange={(e) => setAllEvents(e.target.checked)} /> 显示全部
            </label>
          </div>
          <ul className="diag-list">
            {shown.length ? shown.map((e, i) => (
              <li key={i} data-testid="event-row" data-kind={e.kind}>
                <span className={`badge badge-${eventTone(e)}`}>{e.ts?.slice(11, 19) || ""}</span>
                {describeEvent(e)}
              </li>
            )) : <li className="settings-meta">还没有事件。</li>}
          </ul>
        </section>
      </section>
    </div>
  );
}
