"use client";

// 工作流编排, restored from master 599ed0a (flow-board / flow-stages / flow-inspector layout and CSS).
// workflow data: /api/workflow/workflows (harness YAML). Default model: /api/workflow/models + /api/models/selection
// (shown in 配置面板). Per-agent model + thinking: /api/workflow/agent-models. 加载预设工作流 opens a dialog listing the same catalog.
import { Bot, ChevronLeft, ChevronRight, SlidersHorizontal, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "../../lib/api";
import { label } from "../../lib/labels";
import { modelChoices, type ModelRow } from "../../lib/model-options";
import { THINKING_LEVELS, workflowForMode, type WorkflowNode, type WorkflowCard } from "../../lib/workflow-cards";

export type WorkMode = "new" | "revise";

type Selection =
  | { kind: "workflow" }
  | { kind: "node"; id: string }
  | { kind: "agent"; id: string; agent: string };

export function WorkflowBoard({ mode }: { mode: WorkMode }) {
  const [catalog, setCatalog] = useState<WorkflowCard[]>([]);
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [models, setModels] = useState<ModelRow[]>([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [modelNote, setModelNote] = useState("");
  const [selection, setSelection] = useState<Selection>({ kind: "workflow" });
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [presetsOpen, setPresetsOpen] = useState(false);
  const presetsDialog = useRef<HTMLDialogElement>(null);

  const load = useCallback(async () => {
    try {
      const response = await apiFetch("/api/workflow/workflows", { cache: "no-store" });
      const data = (await response.json()) as { workflows?: WorkflowCard[]; detail?: string };
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      const list = data.workflows || [];
      setCatalog(list);
      setError(list.length ? "" : "没有对应的工作流");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    setPickedId(null);
    setSelection({ kind: "workflow" });
    setPresetsOpen(false);
    void load();
  }, [mode, load]);

  useEffect(() => {
    const dialog = presetsDialog.current;
    if (!dialog) return;
    if (presetsOpen && !dialog.open) dialog.showModal();
    if (!presetsOpen && dialog.open) dialog.close();
  }, [presetsOpen]);

  useEffect(() => {
    apiFetch("/api/workflow/models")
      .then((r) => r.json() as Promise<{ default_ref?: string; default?: string; models?: ModelRow[] }>)
      .then((d) => {
        setModels(d.models || []);
        setDefaultModel(d.default_ref || d.default || "");
      })
      .catch(() => setModels([]));
  }, []);

  const workflow = useMemo(() => {
    if (pickedId) {
      return catalog.find((w) => w.id === pickedId) || workflowForMode(catalog, mode) || null;
    }
    return workflowForMode(catalog, mode) || null;
  }, [catalog, pickedId, mode]);

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

  async function changeAgent(node: string, agent: string, model: string, thinking: string) {
    setModelNote("");
    const r = await apiFetch("/api/workflow/agent-models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node, agent, model, thinking }),
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

  function pickPreset(id: string) {
    setPickedId(id);
    setPresetsOpen(false);
    setSelection({ kind: "workflow" });
  }

  if (error) return <p className="status-banner error">{error}</p>;
  if (!workflow) return <p className="settings-help">正在读取编排…</p>;
  const def = modelChoices(models, defaultModel);
  const node = selection.kind === "node" || selection.kind === "agent"
    ? workflow.details.find((n) => n.id === selection.id)
    : undefined;

  return (
    <div className="flow-board" data-inspector={inspectorOpen ? "true" : "false"} data-testid="workflow-board">
      <div className="flow-toolbar">
        <button
          type="button"
          className="flow-presets"
          data-testid="flow-load-presets"
          aria-pressed={presetsOpen}
          onClick={() => setPresetsOpen(true)}
        >
          加载预设工作流
        </button>
        <button type="button" className="flow-config" onClick={() => choose({ kind: "workflow" })}>
          <SlidersHorizontal size={16} strokeWidth={1.75} aria-hidden="true" />
          配置面板
        </button>
      </div>

      <div className="flow-stages">
        {workflow.details.map((n, index) => {
          const active = (selection.kind === "node" || selection.kind === "agent") && selection.id === n.id;
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
                  {Object.keys(n.agents).map((name) => (
                    <button key={name} type="button" className="flow-step" data-agent={name}
                      data-testid={`flow-agent-${n.id}-${name}`}
                      aria-pressed={selection.kind === "agent" && selection.id === n.id && selection.agent === name}
                      onClick={() => choose({ kind: "agent", id: n.id, agent: name })}>
                      <span className="flow-step-agent">
                        <Bot className="flow-step-icon" size={15} strokeWidth={1.75} aria-hidden="true" />
                        <em>{label(name)}</em>
                      </span>
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
            <section className="flow-detail" data-testid="flow-workflow-config">
              <h3>{workflow.title || workflow.id}</h3>
              <p className="settings-meta">计划文件 {workflow.plan_file}{workflow.start_rev === "next" ? " · 在已有产物上修订" : ""}</p>
              <h4>默认模型</h4>
              <select
                className="flow-model"
                data-testid="flow-default-model"
                aria-label="默认模型"
                value={def.value}
                onChange={(e) => void changeDefault(e.target.value)}
              >
                {def.choices.map((c) => (
                  <option key={c.value || "none"} value={c.value} disabled={!c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
              {modelNote ? <p className="flow-model-note" data-testid="flow-model-note">{modelNote}</p> : null}
              <h4>节点</h4>
              <ol>
                {workflow.details.map((n) => (
                  <li key={n.id}>
                    <button type="button" className="flow-back" onClick={() => choose({ kind: "node", id: n.id })}>{n.title || n.id}</button>
                  </li>
                ))}
              </ol>
            </section>
          ) : node && selection.kind === "node" ? (
            <NodeDetail node={node} onAgent={(agent) => choose({ kind: "agent", id: node.id, agent })} />
          ) : node && selection.kind === "agent" ? (
            <AgentDetail node={node} agentKey={selection.agent} models={models} onChange={changeAgent} note={modelNote} />
          ) : null}
        </aside>
      ) : null}

      <dialog
        ref={presetsDialog}
        className="flow-presets-dialog"
        aria-labelledby="flow-presets-title"
        data-testid="flow-presets-dialog"
        onClose={() => setPresetsOpen(false)}
        onClick={(event) => {
          if (event.target === presetsDialog.current) setPresetsOpen(false);
        }}
      >
        <div className="flow-presets-panel">
          <header className="flow-presets-head">
            <div>
              <h2 id="flow-presets-title">加载预设工作流</h2>
              <p className="settings-meta">选择 harness 编排，立即替换画布上的节点预览（不改计划正文；开始运行仍按计划页工作类型选编排）。</p>
            </div>
            <button type="button" className="flow-close" aria-label="关闭" data-testid="flow-presets-close" onClick={() => setPresetsOpen(false)}>
              <X size={16} strokeWidth={1.75} aria-hidden="true" />
            </button>
          </header>
          <ul className="flow-preset-list">
            {catalog.map((w) => {
              const active = w.id === workflow.id;
              const kind = w.start_rev === "next" ? "修订" : w.id.startsWith("demo") ? "演示" : "主流程";
              return (
                <li key={w.id}>
                  <button
                    type="button"
                    className="flow-preset-item"
                    data-active={active ? "true" : "false"}
                    data-testid={`flow-preset-${w.id}`}
                    aria-pressed={active}
                    onClick={() => pickPreset(w.id)}
                  >
                    <strong>{w.title || w.id}</strong>
                    <small className="settings-meta">{kind} · {w.id} · {w.plan_file} · {w.details.length} 节点</small>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </dialog>
    </div>
  );
}

function NodeDetail({ node, onAgent }: { node: WorkflowNode; onAgent: (agent: string) => void }) {
  return (
    <section className="flow-detail" data-testid={`flow-node-detail-${node.id}`}>
      <h3>{node.title || node.id}</h3>
      <p className="settings-meta">{node.id} · 最多 {node.max_rounds} 轮</p>
      <div className="flow-block">
        <h4>输入</h4>
        <ul className="flow-path-list">
          {node.requires.length ? node.requires.map((r) => (
            <li key={r}><code className="flow-path-chip">{r}</code></li>
          )) : <li className="flow-empty">无</li>}
        </ul>
      </div>
      <div className="flow-block">
        <h4>产出</h4>
        <ul className="flow-path-list">
          {node.produces.map((p) => (
            <li key={p.path}>
              <code className="flow-path-chip">{p.path}</code>
              <span className="flow-path-spec">规格 {p.spec}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="flow-block">
        <h4>代理</h4>
        <div className="flow-agent-chips">
          {Object.keys(node.agents).map((name) => (
            <button
              key={name}
              type="button"
              className="flow-agent-chip"
              data-agent={name}
              onClick={() => onAgent(name)}
            >
              {label(name)}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function AgentDetail({ node, agentKey, models, onChange, note }: {
  node: WorkflowNode; agentKey: string; models: ModelRow[];
  onChange: (node: string, agent: string, model: string, thinking: string) => Promise<void>;
  note: string;
}) {
  const agent = node.agents[agentKey];
  if (!agent) return null;
  const gm = agent.gui_model || "";
  const gt = agent.gui_thinking || "";
  const choices = modelChoices(models, gm).choices.filter((c) => c.value);
  return (
    <section className="flow-detail" data-testid={`flow-agent-detail-${node.id}-${agentKey}`}>
      <h3>{node.title || node.id} · {label(agentKey)}</h3>
      <p className="settings-meta">agent {agent.template || "内联"} · 当前模型 {agent.model}{agent.thinking ? ` · 思考 ${agent.thinking}` : ""}</p>
      <div className="flow-block">
        <h4>模型</h4>
        <select className="flow-model" data-testid="agent-model-select" value={gm} onChange={(e) => void onChange(node.id, agentKey, e.target.value, gt)}>
          <option value="">使用默认模型</option>
          {choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <h4>思考</h4>
        <select className="flow-model" data-testid="agent-thinking-select" value={gt} onChange={(e) => void onChange(node.id, agentKey, gm, e.target.value)}>
          {THINKING_LEVELS.map((t) => <option key={t || "default"} value={t}>{t || "模型默认"}</option>)}
        </select>
        {note ? <p className="flow-model-note" data-testid="flow-model-note">{note}</p> : null}
      </div>
      <div className="flow-block">
        <h4>可读</h4>
        <ul className="flow-path-list">
          {agent.read.map((g) => <li key={g}><code className="flow-path-chip">{g}</code></li>)}
        </ul>
        <h4>可写</h4>
        <ul className="flow-path-list">
          {agent.write.length ? agent.write.map((g) => <li key={g}><code className="flow-path-chip">{g}</code></li>) : <li className="flow-empty">无</li>}
        </ul>
      </div>
      <div className="flow-block">
        <h4>工具</h4>
        <ul className="flow-plain-list">
          <li>文件工具{agentKey === "executor" ? "（含写入）" : "（只读）"}、submit</li>
          {agent.tools.mcp.map((m) => <li key={m}>MCP：{m}</li>)}
          {agent.tools.skills.map((s) => <li key={s}>技能：{s}</li>)}
        </ul>
        <h4>规则</h4>
        <ul className="flow-path-list">
          {agent.rules.length ? agent.rules.map((r) => <li key={r}><code className="flow-path-chip">{r}</code></li>) : <li className="flow-empty">只有全局规则</li>}
        </ul>
      </div>
    </section>
  );
}
