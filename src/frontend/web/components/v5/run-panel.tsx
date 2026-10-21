"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "../../lib/api";
import { initialWorkflow } from "../../lib/initial-workflow";
import { modelChoices, type ModelRow } from "../../lib/model-options";

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

const STATUS_LABEL: Record<string, string> = {
  idle: "空闲",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  pending: "等待",
  passed: "通过",
  stopped: "已停止",
  error: "错误",
};

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

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 2000);
    return () => clearInterval(timer);
  }, [refresh]);

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

  return (
    <section className="v5-run-panel" style={{ display: "grid", gap: 12, padding: 16 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
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
        {modelNote ? <small className="settings-help" data-testid="model-note">提示：{modelNote}</small> : null}
        <button data-testid="run-start" type="button" onClick={() => void act("start")} disabled={busy || run?.running}>
          开始运行
        </button>
        <button data-testid="run-stop" type="button" onClick={() => void act("stop")} disabled={busy || !run?.running}>
          停止
        </button>
        <button data-testid="run-resume" type="button" onClick={() => void act("resume")} disabled={busy || run?.running || !run?.run_id}>
          续跑
        </button>
        <span>
          状态：
          <strong data-testid="run-status" data-status={status}>
            {STATUS_LABEL[status] || status}
          </strong>
          {run?.reason ? <span data-testid="run-reason">（{run.reason}）</span> : null}
        </span>
      </div>
      {error ? (
        <p data-testid="run-error" role="alert" style={{ color: "#b42318" }}>
          {error}
        </p>
      ) : null}
      <table data-testid="node-table" style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th align="left">节点</th>
            <th align="left">状态</th>
            <th align="left">轮次</th>
            <th align="left">反馈</th>
            <th align="left">错误</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((node) => (
            <tr key={node.id} data-testid={`node-row-${node.id}`} data-status={node.status}>
              <td>
                {node.id}
                {cards.get(node.id)?.title ? ` · ${cards.get(node.id)?.title}` : ""}
              </td>
              <td>{STATUS_LABEL[node.status] || node.status}</td>
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
      {feedback ? (
        <div data-testid="feedback-view">
          <h3>
            {feedback.node} 第 {feedback.round} 轮反馈
          </h3>
          <pre style={{ whiteSpace: "pre-wrap" }}>{feedback.text}</pre>
        </div>
      ) : null}
      {wf ? (
        <div style={{ display: "grid", gap: 8 }}>
          {wf.details.map((node) => (
            <details key={node.id} data-testid={`node-card-${node.id}`}>
              <summary>
                {node.id}：交付 {node.produces.map((p) => `${p.spec} → artifacts/${p.path}`).join("，") || "无"}
                {node.requires.length ? `；需要 ${node.requires.join("，")}` : ""}；最多 {node.max_rounds} 轮
              </summary>
              {Object.entries(node.agents).map(([name, a]) => (
                <div key={name} data-testid={`agent-card-${node.id}-${name}`} style={{ paddingLeft: 12 }}>
                  <strong>{name}</strong>：{a.model} / 思考 {a.thinking} / 角色 {a.role}
                  <div>工具：文件工具{a.tools.mcp.length ? `、MCP ${a.tools.mcp.join("、")}` : ""}{a.tools.skills.length ? `、技能 ${a.tools.skills.join("、")}` : ""}</div>
                  <div>规则：{a.rules.length ? a.rules.join("、") : "仅全局规则"}</div>
                  <div>可写：{a.write.join("、")}</div>
                  <div>可读：{a.read.join("、")}</div>
                </div>
              ))}
            </details>
          ))}
        </div>
      ) : null}
    </section>
  );
}
