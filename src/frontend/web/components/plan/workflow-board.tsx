"use client";

// 工作流编排, restored from master 599ed0a (flow-board / flow-stages / flow-inspector layout and CSS).
// v5 data: /api/v5/workflows (harness YAML). Default model: /api/workflow/models + /api/models/selection.
// Per-agent model + thinking: /api/v5/agent-models (GUI setting, applied at run start; empty = default).
import { Bot, ChevronLeft, ChevronRight, SlidersHorizontal, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import { label } from "../../lib/labels";
import { modelChoices, type ModelRow } from "../../lib/model-options";
import { THINKING_LEVELS, workflowForMode, type V5Node, type V5Workflow } from "../../lib/v5-workflow";

export type WorkMode = "new" | "revise";

type Selection = { kind: "workflow" } | { kind: "node"; id: string } | { kind: "agent"; id: string; role: string };

export function WorkflowBoard({ mode }: { mode: WorkMode }) {
  const [workflow, setWorkflow] = useState<V5Workflow | null>(null);
  const [error, setError] = useState("");
  const [models, setModels] = useState<ModelRow[]>([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [modelNote, setModelNote] = useState("");
  const [selection, setSelection] = useState<Selection>({ kind: "workflow" });
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await apiFetch("/api/v5/workflows", { cache: "no-store" });
      const data = (await response.json()) as { workflows?: V5Workflow[]; detail?: string };
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      const wf = workflowForMode(data.workflows || [], mode);
      setWorkflow(wf || null);
      setError(wf ? "" : "没有对应的工作流");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [mode]);

  useEffect(() => {
    setSelection({ kind: "workflow" });
    void load();
  }, [load]);

  useEffect(() => {
    apiFetch("/api/workflow/models")
      .then((r) => r.json() as Promise<{ default_ref?: string; default?: string; models?: ModelRow[] }>)
      .then((d) => {
        setModels(d.models || []);
        setDefaultModel(d.default_ref || d.default || "");
      })
      .catch(() => setModels([]));
  }, []);

  async function changeDefault(value: string) {
    setModelNote("");
    const r = await apiFetch("/api/models/selection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: value }),
    });
    if (r.ok) {
      setDefaultModel(value);
      setModelNote("已保存，下次运行生效");
      void load();
    } else setModelNote(`保存失败（HTTP ${r.status}）`);
  }

  async function changeAgent(node: string, role: string, model: string, thinking: string) {
    setModelNote("");
    const r = await apiFetch("/api/v5/agent-models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node, role, model, thinking }),
    });
    if (r.ok) {
      setModelNote("已保存，下次运行开始时生效");
      void load();
    } else {
      const d = (await r.json().catch(() => ({}))) as { detail?: string };
      setModelNote(d.detail || `保存失败（HTTP ${r.status}）`);
    }
  }

  function choose(next: Selection) {
    setSelection(next);
    setInspectorOpen(true);
  }

  if (error) return <p className="status-banner error">{error}</p>;
  if (!workflow) return <p className="settings-help">正在读取编排…</p>;
  const def = modelChoices(models, defaultModel);
  const node = selection.kind !== "workflow" ? workflow.details.find((n) => n.id === selection.id) : undefined;

  return (
    <div className="flow-board" data-inspector={inspectorOpen ? "true" : "false"} data-testid="workflow-board">
      <div className="flow-toolbar">
        <label className="flow-toolbar-model">
          <span>默认模型</span>
          <select className="flow-model" aria-label="默认模型" value={def.value} onChange={(e) => void changeDefault(e.target.value)}>
            {def.choices.map((c) => (
              <option key={c.value || "none"} value={c.value} disabled={!c.value}>
                {c.label}
              </option>
            ))}
          </select>
          {modelNote ? <span className="flow-model-note" data-testid="flow-model-note">{modelNote}</span> : null}
        </label>
        <button type="button" className="flow-config" onClick={() => choose({ kind: "workflow" })}>
          <SlidersHorizontal size={16} strokeWidth={1.75} aria-hidden="true" />
          配置面板
        </button>
      </div>

      <div className="flow-stages">
        {workflow.details.map((n, index) => {
          const active = selection.kind !== "workflow" && selection.id === n.id;
          return (
            <div className="flow-stage-wrap" key={n.id}>
              {index > 0 ? (
                <div className="flow-arrow" aria-hidden="true">
                  <ChevronRight size={16} />
                </div>
              ) : null}
              <article className="flow-stage" data-active={active ? "true" : "false"} data-testid={`flow-node-${n.id}`}
                onClick={() => choose({ kind: "node", id: n.id })}>
                <button type="button" className="flow-stage-head" aria-pressed={active}
                  onClick={(e) => { e.stopPropagation(); choose({ kind: "node", id: n.id }); }}>
                  <span className="flow-stage-index">{String(index + 1).padStart(2, "0")}</span>
                  <strong>{n.title || n.id}</strong>
                  <small>最多 {n.max_rounds} 轮 · {n.id}</small>
                </button>
                <div className="flow-steps" onClick={(e) => e.stopPropagation()}>
                  {Object.entries(n.agents).map(([name, agent]) => (
                    <button key={name} type="button" className="flow-step" data-role={agent.role}
                      data-testid={`flow-agent-${n.id}-${name}`}
                      aria-pressed={selection.kind === "agent" && selection.id === n.id && selection.role === name}
                      onClick={() => choose({ kind: "agent", id: n.id, role: name })}>
                      <span className="flow-step-role">
                        <Bot className="flow-step-icon" size={15} strokeWidth={1.75} aria-hidden="true" />
                        <em>{label(name)}</em>
                      </span>
                      <small className="flow-step-meta">
                        {agent.model_source === "default" ? <span>默认</span> : null}
                        <span>{agent.model}</span>
                        {agent.thinking ? <span>思考 {agent.thinking}</span> : null}
                      </small>
                    </button>
                  ))}
                </div>
              </article>
            </div>
          );
        })}
      </div>

      {inspectorOpen ? (
        <aside className="flow-inspector" aria-live="polite" data-testid="flow-inspector">
          {selection.kind !== "workflow" ? (
            <button type="button" className="flow-back" onClick={() => setSelection({ kind: "workflow" })}>
              <ChevronLeft size={16} strokeWidth={1.75} aria-hidden="true" />
              回到全局规则
            </button>
          ) : null}
          <button type="button" className="flow-close" aria-label="关闭" onClick={() => setInspectorOpen(false)}>
            <X size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
          {selection.kind === "workflow" ? (
            <section>
              <h3>{workflow.title || workflow.id}</h3>
              <p className="settings-meta">计划文件 {workflow.plan_file}{workflow.revise_of ? ` · 修订自 ${workflow.revise_of}` : ""}</p>
              <ol>
                {workflow.details.map((n) => (
                  <li key={n.id}>
                    <button type="button" className="flow-back" onClick={() => choose({ kind: "node", id: n.id })}>{n.title || n.id}</button>
                  </li>
                ))}
              </ol>
            </section>
          ) : node && selection.kind === "node" ? (
            <NodeDetail node={node} onAgent={(role) => choose({ kind: "agent", id: node.id, role })} />
          ) : node && selection.kind === "agent" ? (
            <AgentDetail node={node} role={selection.role} models={models} onChange={changeAgent} />
          ) : null}
        </aside>
      ) : null}
    </div>
  );
}

function NodeDetail({ node, onAgent }: { node: V5Node; onAgent: (role: string) => void }) {
  return (
    <section data-testid={`flow-node-detail-${node.id}`}>
      <h3>{node.title || node.id}</h3>
      <p className="settings-meta">{node.id} · 最多 {node.max_rounds} 轮</p>
      <h4>输入</h4>
      <ul>{node.requires.length ? node.requires.map((r) => <li key={r} className="mono">{r}</li>) : <li>无</li>}</ul>
      <h4>产出</h4>
      <ul>{node.produces.map((p) => <li key={p.path}><span className="mono">{p.path}</span>（规格 {p.spec}）</li>)}</ul>
      <h4>代理</h4>
      <ul>
        {Object.keys(node.agents).map((name) => (
          <li key={name}><button type="button" className="flow-back" onClick={() => onAgent(name)}>{label(name)}</button></li>
        ))}
      </ul>
    </section>
  );
}

function AgentDetail({ node, role, models, onChange }: {
  node: V5Node; role: string; models: ModelRow[];
  onChange: (node: string, role: string, model: string, thinking: string) => Promise<void>;
}) {
  const agent = node.agents[role];
  if (!agent) return null;
  const gm = agent.gui_model || "";
  const gt = agent.gui_thinking || "";
  const choices = modelChoices(models, gm).choices.filter((c) => c.value);
  return (
    <section data-testid={`flow-agent-detail-${node.id}-${role}`}>
      <h3>{node.title || node.id} · {label(role)}</h3>
      <p className="settings-meta">角色 {agent.role} · 当前模型 {agent.model}{agent.thinking ? ` · 思考 ${agent.thinking}` : ""}</p>
      <h4>模型</h4>
      <select className="flow-model" data-testid="agent-model-select" value={gm} onChange={(e) => void onChange(node.id, role, e.target.value, gt)}>
        <option value="">使用默认模型</option>
        {choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </select>
      <h4>思考</h4>
      <select className="flow-model" data-testid="agent-thinking-select" value={gt} onChange={(e) => void onChange(node.id, role, gm, e.target.value)}>
        {THINKING_LEVELS.map((t) => <option key={t || "default"} value={t}>{t || "模型默认"}</option>)}
      </select>
      <h4>可读</h4>
      <ul>{agent.read.map((g) => <li key={g} className="mono">{g}</li>)}</ul>
      <h4>可写</h4>
      <ul>{agent.write.length ? agent.write.map((g) => <li key={g} className="mono">{g}</li>) : <li>无</li>}</ul>
      <h4>工具</h4>
      <ul>
        <li>文件工具{role === "executor" ? "（含写入）" : "（只读）"}、submit</li>
        {agent.tools.mcp.map((m) => <li key={m}>MCP：{m}</li>)}
        {agent.tools.skills.map((s) => <li key={s}>技能：{s}</li>)}
      </ul>
      <h4>规则</h4>
      <ul>{agent.rules.length ? agent.rules.map((r) => <li key={r} className="mono">{r}</li>) : <li>只有全局规则</li>}</ul>
    </section>
  );
}
