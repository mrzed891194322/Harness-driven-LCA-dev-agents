"use client";

// 工作流编排, restored from master 599ed0a (flow-board / flow-stages / flow-inspector layout and CSS).
// workflow data: /api/workflow/workflows (harness YAML). Default model: /api/workflow/models + /api/models/selection
// (shown in 配置面板). Per-agent model + thinking: /api/workflow/agent-models.
// 加载预设 / 节点内代理拓扑均为 dialog；拓扑来自节点 YAML flow（静态），不含运行时状态。
import { ArrowDownToLine, ArrowUpFromLine, Bot, Boxes, ChevronRight, Cpu, FileText, ScrollText, Shield, SlidersHorizontal, Workflow, Wrench, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Fragment, useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { apiFetch } from "../../lib/api";
import { label } from "../../lib/labels";
import { modelChoices, type ModelRow } from "../../lib/model-options";
import { THINKING_LEVELS, workflowForMode, type WorkflowNode, type WorkflowCard, type WorkflowRuleCard } from "../../lib/workflow-cards";

export type WorkMode = "new" | "revise";

type Selection =
  | { kind: "workflow" }
  | { kind: "node"; id: string }
  | { kind: "agent"; id: string; agent: string }
  | { kind: "rule"; path: string; title?: string };

export function WorkflowBoard({ mode }: { mode: WorkMode }) {
  const [catalog, setCatalog] = useState<WorkflowCard[]>([]);
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [models, setModels] = useState<ModelRow[]>([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [defaultThinking, setDefaultThinking] = useState("");
  const [modelNote, setModelNote] = useState("");
  const [selection, setSelection] = useState<Selection>({ kind: "workflow" });
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [presetsOpen, setPresetsOpen] = useState(false);
  const presetsDialog = useRef<HTMLDialogElement>(null);
  const [topoNodeId, setTopoNodeId] = useState<string | null>(null);
  const topoDialog = useRef<HTMLDialogElement>(null);

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
    setTopoNodeId(null);
    void load();
  }, [mode, load]);

  useEffect(() => {
    const dialog = presetsDialog.current;
    if (!dialog) return;
    if (presetsOpen && !dialog.open) dialog.showModal();
    if (!presetsOpen && dialog.open) dialog.close();
  }, [presetsOpen]);

  useEffect(() => {
    const dialog = topoDialog.current;
    if (!dialog) return;
    if (topoNodeId && !dialog.open) dialog.showModal();
    if (!topoNodeId && dialog.open) dialog.close();
  }, [topoNodeId]);

  useEffect(() => {
    apiFetch("/api/workflow/models")
      .then((r) => r.json() as Promise<{ default_ref?: string; default?: string; thinking?: string; models?: ModelRow[] }>)
      .then((d) => {
        setModels(d.models || []);
        setDefaultModel(d.default_ref || d.default || "");
        setDefaultThinking(d.thinking || "");
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

  async function changeDefaultThinking(thinking: string) {
    setModelNote("");
    const r = await apiFetch("/api/models/selection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: defaultModel, thinking }),
    });
    if (r.ok) {
      setDefaultThinking(thinking);
      setModelNote("已保存，下次运行生效");
      void load();
    } else {
      const d = (await r.json().catch(() => ({}))) as { detail?: string };
      setModelNote(d.detail || `保存失败（HTTP ${r.status}）`);
    }
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
                <div
                  className="flow-steps"
                  role="button"
                  tabIndex={0}
                  data-testid={`flow-agents-box-${n.id}`}
                  aria-label={`${n.title || n.id} 代理拓扑`}
                  onClick={(e) => { e.stopPropagation(); setTopoNodeId(n.id); }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      e.stopPropagation();
                      setTopoNodeId(n.id);
                    }
                  }}
                >
                  {Object.keys(n.agents).map((name) => (
                    <button key={name} type="button" className="flow-step" data-agent={name}
                      data-testid={`flow-agent-${n.id}-${name}`}
                      aria-pressed={selection.kind === "agent" && selection.id === n.id && selection.agent === name}
                      title="在侧栏配置模型"
                      onClick={(e) => { e.stopPropagation(); choose({ kind: "agent", id: n.id, agent: name }); }}>
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
          <FlowCrumb selection={selection} onSelect={setSelection} />
          <button type="button" className="flow-close" aria-label="关闭" onClick={() => setInspectorOpen(false)}>
            <X size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
          {selection.kind === "workflow" ? (
            <WorkflowConfig
              workflow={workflow}
              def={def}
              modelNote={modelNote}
              thinking={defaultThinking}
              thinkingLevels={thinkingLevelsFor(models, defaultModel)}
              onChangeDefault={(v) => void changeDefault(v)}
              onChangeThinking={(v) => void changeDefaultThinking(v)}
              onPickNode={(id) => choose({ kind: "node", id })}
              onPickRule={(path, title) => choose({ kind: "rule", path, title })}
            />
          ) : selection.kind === "rule" ? (
            <RuleDetail path={selection.path} title={selection.title} onBack={() => setSelection({ kind: "workflow" })} />
          ) : node && selection.kind === "node" ? (
            <NodeDetail
              node={node}
              globalRules={workflow.global_rules || []}
              onOpenTopo={() => setTopoNodeId(node.id)}
              onPickRule={(path, title) => choose({ kind: "rule", path, title })}
            />
          ) : node && selection.kind === "agent" ? (
            <AgentDetail
              node={node}
              agentKey={selection.agent}
              models={models}
              onChange={changeAgent}
              note={modelNote}
              globalRules={workflow.global_rules || []}
              onPickRule={(path, title) => choose({ kind: "rule", path, title })}
            />
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

      <dialog
        ref={topoDialog}
        className="flow-presets-dialog flow-topo-dialog"
        aria-labelledby="flow-topo-title"
        data-testid="flow-topo-dialog"
        onClose={() => setTopoNodeId(null)}
        onClick={(event) => {
          if (event.target === topoDialog.current) setTopoNodeId(null);
        }}
      >
        {(() => {
          const topoNode = workflow.details.find((n) => n.id === topoNodeId);
          if (!topoNode) return null;
          return (
            <AgentTopoPanel
              node={topoNode}
              onClose={() => setTopoNodeId(null)}
              onConfigureAgent={(agent) => {
                setTopoNodeId(null);
                choose({ kind: "agent", id: topoNode.id, agent });
              }}
            />
          );
        })()}
      </dialog>
    </div>
  );
}

const FLOW_WHEN: Record<string, string> = {
  done: "完成",
  blocked: "受阻",
  redo_upstream: "回溯上游",
  approve: "通过",
  reject: "退回",
  approve_redo_upstream: "批准回溯",
  terminate: "终止",
  failed: "失败",
};

const FLOW_TERMINALS = new Set(["done", "failed", "blocked", "redo_upstream"]);

function flowWhenLabel(when: string | null | undefined) {
  if (!when) return "无条件";
  return FLOW_WHEN[when] || when;
}

function mermaidId(raw: string) {
  const id = raw.replace(/[^a-zA-Z0-9_]/g, "_");
  return /^[0-9]/.test(id) ? `n_${id}` : id || "node";
}

/** Static mermaid from node YAML flow.edges (no runtime / LangGraph draw). */
function flowToMermaid(node: WorkflowNode): string {
  const edges = node.flow?.edges || [];
  const agents = Object.keys(node.agents);
  const start = node.flow?.start || agents[0] || "";
  const terminals = new Set<string>();
  for (const e of edges) {
    if (FLOW_TERMINALS.has(e.to)) terminals.add(e.to);
  }
  const lines: string[] = ["graph LR"];
  for (const name of agents) {
    const primary = node.agents[name]?.submit === "artifact";
    const base = label(name) || name;
    const title = (primary ? `${base} · 主` : base).replace(/"/g, "#quot;");
    if (primary || name === start) lines.push(`  ${mermaidId(name)}(["${title}"])`);
    else lines.push(`  ${mermaidId(name)}["${title}"]`);
  }
  for (const term of terminals) {
    const title = (FLOW_WHEN[term] || term).replace(/"/g, "#quot;");
    lines.push(`  ${mermaidId(term)}((${title}))`);
  }
  for (const e of edges) {
    const w = `${flowWhenLabel(e.when)}${e.max != null ? ` ·≤${e.max}` : ""}`.replace(/"/g, "#quot;");
    lines.push(`  ${mermaidId(e.from)} -->|"${w}"| ${mermaidId(e.to)}`);
  }
  for (const name of agents) {
    const submit = node.agents[name]?.submit;
    const cls =
      submit === "artifact" || name === "executor" ? "executorCls"
      : name === "reviewer" || submit === "verdict" ? "reviewerCls"
      : name === "reviser" ? "reviserCls"
      : "executorCls";
    lines.push(`  class ${mermaidId(name)} ${cls}`);
  }
  lines.push("  classDef executorCls fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20,stroke-width:2px");
  lines.push("  classDef reviewerCls fill:#fff3e0,stroke:#ef6c00,color:#e65100,stroke-width:1.5px");
  lines.push("  classDef reviserCls fill:#e3f2fd,stroke:#1565c0,color:#0d47a1,stroke-width:1.5px");
  return lines.join("\n");
}

function MermaidGraph({ chart }: { chart: string }) {
  const host = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");
  const [err, setErr] = useState("");
  useEffect(() => {
    let cancelled = false;
    setErr("");
    void (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          themeVariables: {
            primaryColor: "#e8f5e9",
            primaryTextColor: "#1c1f1a",
            primaryBorderColor: "#2e7d32",
            lineColor: "#6b7280",
            secondaryColor: "#f6f8f4",
            tertiaryColor: "#fff",
            fontFamily: "ui-sans-serif, system-ui, sans-serif",
          },
          flowchart: { curve: "basis", htmlLabels: false, padding: 12 },
        });
        const id = `flow-topo-${reactId}`;
        const { svg } = await mermaid.render(id, chart);
        if (cancelled || !host.current) return;
        host.current.innerHTML = svg;
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
      if (host.current) host.current.innerHTML = "";
    };
  }, [chart, reactId]);
  if (err) return <p className="status-banner error">拓扑图渲染失败：{err}</p>;
  return <div className="flow-topo-mermaid" data-testid="flow-topo-mermaid" ref={host} />;
}

function AgentTopoPanel({
  node,
  onClose,
  onConfigureAgent,
}: {
  node: WorkflowNode;
  onClose: () => void;
  onConfigureAgent: (agent: string) => void;
}) {
  const start = node.flow?.start || Object.keys(node.agents)[0] || "";
  const agentOrder = Object.keys(node.agents).sort((a, b) => {
    const ap = node.agents[a]?.submit === "artifact" ? 0 : 1;
    const bp = node.agents[b]?.submit === "artifact" ? 0 : 1;
    if (ap !== bp) return ap - bp;
    if (a === start) return -1;
    if (b === start) return 1;
    return a.localeCompare(b);
  });
  const chart = useMemo(() => flowToMermaid(node), [node]);

  return (
    <div className="flow-presets-panel">
      <header className="flow-presets-head">
        <div>
          <h2 id="flow-topo-title">{node.title || node.id} · 代理拓扑</h2>
          <p className="settings-meta">静态 YAML flow；主 agent = deliver.submit: artifact。点代理名打开侧栏配置。</p>
        </div>
        <button type="button" className="flow-close" aria-label="关闭" data-testid="flow-topo-close" onClick={onClose}>
          <X size={16} strokeWidth={1.75} aria-hidden="true" />
        </button>
      </header>

      <div className="flow-topo-graph" data-testid="flow-topo-graph">
        <MermaidGraph chart={chart} />
      </div>

      <div className="flow-block flow-topo-agents-list">
        <h4>代理</h4>
        <ul className="flow-topo-agent-list" data-testid="flow-topo-agent-list">
          {agentOrder.map((name) => {
            const primary = node.agents[name]?.submit === "artifact";
            return (
              <li key={name}>
                <button
                  type="button"
                  className="flow-topo-agent-item"
                  data-agent={name}
                  data-primary={primary ? "true" : "false"}
                  data-testid={`flow-topo-pick-${name}`}
                  onClick={() => onConfigureAgent(name)}
                >
                  <strong>{label(name) || name}</strong>
                  {primary ? <span className="flow-topo-primary-badge">主 agent</span> : null}
                  <small className="settings-meta">{name}{node.agents[name]?.template ? ` · ${node.agents[name].template}` : ""}</small>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}


function rulePathLabel(path: string) {
  return path.replace(/^harness\//, "");
}

function FlowCrumb({ selection, onSelect }: {
  selection: Selection;
  onSelect: (next: Selection) => void;
}) {
  const crumbs: { key: string; label: string; target: Selection | null }[] = [];
  if (selection.kind === "workflow") return null;
  crumbs.push({ key: "workflow", label: "全局配置", target: { kind: "workflow" } });
  if (selection.kind === "agent") {
    crumbs.push({ key: selection.id, label: "节点配置", target: { kind: "node", id: selection.id } });
  } else if (selection.kind === "rule") {
    crumbs.push({ key: selection.path, label: selection.title || rulePathLabel(selection.path), target: null });
  }
  return (
    <nav className="flow-crumb" aria-label="配置位置" data-testid="flow-crumb">
      {crumbs.map((crumb, index) => (
        <span className="flow-crumb-step" key={crumb.key}>
          {index > 0 ? <ChevronRight className="flow-crumb-sep" size={14} strokeWidth={1.75} aria-hidden="true" /> : null}
          {crumb.target ? (
            <button type="button" className="flow-crumb-link" onClick={() => onSelect(crumb.target!)}>
              {crumb.label}
            </button>
          ) : (
            <span className="flow-crumb-current" aria-current="page">{crumb.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

function FlowSection({ title, testId, icon: Icon, collapsible = true, defaultOpen = false, children }: {
  title: string;
  testId?: string;
  icon?: LucideIcon;
  collapsible?: boolean;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const heading = (
    <>
      {Icon ? <Icon className="flow-block-icon" size={15} strokeWidth={1.75} aria-hidden="true" /> : null}
      <h4>{title}</h4>
    </>
  );
  if (!collapsible) {
    return (
      <div className="flow-block" data-testid={testId}>
        <div className="flow-block-head">{heading}</div>
        <div className="flow-block-body">{children}</div>
      </div>
    );
  }
  return (
    <details
      className="flow-block"
      data-testid={testId}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        {heading}
        <ChevronRight className="flow-block-chevron" size={14} strokeWidth={1.75} aria-hidden="true" />
      </summary>
      <div className="flow-block-body">{children}</div>
    </details>
  );
}

function thinkingLevelsFor(models: ModelRow[], modelId: string): string[] {
  const row = models.find((item) => item.id === modelId);
  if (!row?.reasoning) return [];
  const known = new Set(THINKING_LEVELS.filter(Boolean));
  const listed = (row.thinking_levels || []).filter((level) => known.has(level));
  return listed.length ? listed : [...known];
}

function WorkflowConfig({
  workflow,
  def,
  modelNote,
  thinking,
  thinkingLevels,
  onChangeDefault,
  onChangeThinking,
  onPickNode,
  onPickRule,
}: {
  workflow: WorkflowCard;
  def: { value: string; choices: { value: string; label: string; disabled?: boolean }[] };
  modelNote: string;
  thinking: string;
  thinkingLevels: string[];
  onChangeDefault: (value: string) => void;
  onChangeThinking: (value: string) => void;
  onPickNode: (id: string) => void;
  onPickRule: (path: string, title?: string) => void;
}) {
  const globalRules: WorkflowRuleCard[] = workflow.global_rules || [];

  return (
    <section className="flow-detail" data-testid="flow-workflow-config">
      <h3>{workflow.title || workflow.id}</h3>
      <p className="settings-meta">
        {workflow.id} · 计划文件 {workflow.plan_file}
        {workflow.start_rev === "next" ? " · 在已有产物上修订" : ""}
        {workflow.max_redos != null ? ` · 最多回溯 ${workflow.max_redos} 次` : ""}
      </p>

      <div className="flow-block" data-testid="flow-default-model-block">
        <div className="flow-block-head">
          <Cpu className="flow-block-icon" size={15} strokeWidth={1.75} aria-hidden="true" />
          <h4>默认模型</h4>
        </div>
        <div className="flow-block-body">
          <select
            className="flow-model"
            data-testid="flow-default-model"
            aria-label="默认模型"
            value={def.value}
            onChange={(e) => onChangeDefault(e.target.value)}
          >
            {def.choices.map((c) => (
              <option key={c.value || "none"} value={c.value} disabled={!c.value}>
                {c.label}
              </option>
            ))}
          </select>
          {thinkingLevels.length ? (
            <>
              <label className="flow-default-thinking-label" htmlFor="flow-default-thinking">思考深度</label>
              <select
                id="flow-default-thinking"
                className="flow-model"
                data-testid="flow-default-thinking"
                aria-label="默认思考深度"
                value={thinking}
                onChange={(e) => onChangeThinking(e.target.value)}
              >
                <option value="">不指定</option>
                {(thinkingLevels.includes(thinking) || !thinking ? thinkingLevels : [thinking, ...thinkingLevels]).map((level) => (
                  <option key={level} value={level}>{level}</option>
                ))}
              </select>
            </>
          ) : null}
          {modelNote ? <p className="flow-model-note" data-testid="flow-model-note">{modelNote}</p> : null}
        </div>
      </div>

      <FlowSection title="节点" testId="flow-nodes" icon={Boxes} collapsible={false}>
        <ul className="flow-node-pick-list">
          {workflow.details.map((n) => (
            <li key={n.id}>
              <button type="button" className="flow-node-pick" onClick={() => onPickNode(n.id)}>
                <span className="flow-option-title">
                  <Workflow className="flow-option-icon" size={14} strokeWidth={1.75} aria-hidden="true" />
                  <strong>{n.title || n.id}</strong>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </FlowSection>

      <FlowSection title="全局规则" testId="flow-rules-global" icon={ScrollText} collapsible={false}>
        <ul className="flow-path-list">
          {globalRules.length ? globalRules.map((r) => (
            <li key={r.path}>
              <button type="button" className="flow-rule-link" onClick={() => onPickRule(r.path, r.title)}>
                {rulePathLabel(r.path)}
              </button>
            </li>
          )) : <li className="flow-empty">无</li>}
        </ul>
      </FlowSection>
    </section>
  );
}

function RuleDetail({ path, title, onBack }: { path: string; title?: string; onBack: () => void }) {
  const [raw, setRaw] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const rel = rulePathLabel(path);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr("");
    setRaw("");
    void apiFetch("/api/workflow/harness", { cache: "no-store" })
      .then(async (r) => {
        const data = (await r.json()) as {
          sections?: { id: string; files?: { path: string; raw?: string; fields?: { title?: string } | null }[] }[];
          detail?: string;
        };
        if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
        const files = (data.sections || []).flatMap((s) => s.files || []);
        const hit = files.find((f) => f.path === path || f.path === `harness/${rel}` || f.path.endsWith(`/${rel}`) || f.path === rel);
        if (!hit?.raw) throw new Error("未在 harness 视图中找到该规则文件");
        if (!cancelled) setRaw(hit.raw);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [path, rel]);

  return (
    <section className="flow-detail" data-testid="flow-rule-detail">
      <h3>{title || rel}</h3>
      <p className="settings-meta">{rel}</p>
      {loading ? <p className="settings-help">正在读取规则…</p> : null}
      {err ? (
        <div className="flow-block">
          <p className="status-banner error">{err}</p>
          <p className="flow-agent-hint">路径：<code className="mono">{rel}</code></p>
          <button type="button" className="flow-back" onClick={onBack}>返回配置面板</button>
        </div>
      ) : null}
      {!loading && !err ? (
        <FlowSection title="内容" icon={FileText}>
          <pre className="flow-code flow-rule-source"><code>{raw}</code></pre>
        </FlowSection>
      ) : null}
    </section>
  );
}


function NodeDetail({ node, globalRules, onOpenTopo, onPickRule }: {
  node: WorkflowNode;
  globalRules: WorkflowRuleCard[];
  onOpenTopo: () => void;
  onPickRule: (path: string, title?: string) => void;
}) {
  const injected = node.inject || [];
  const globals = globalRules || [];
  return (
    <section className="flow-detail" data-testid={`flow-node-detail-${node.id}`}>
      <h3>{node.title || node.id}</h3>
      <p className="settings-meta">{node.id} · 最多 {node.max_rounds} 轮</p>
      <div
        className="flow-block flow-agents-block"
        role="button"
        tabIndex={0}
        data-testid="flow-agents-section"
        aria-label="打开代理拓扑"
        onClick={onOpenTopo}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onOpenTopo();
          }
        }}
      >
        <div className="flow-block-head">
          <Bot className="flow-block-icon" size={15} strokeWidth={1.75} aria-hidden="true" />
          <h4>Agents</h4>
        </div>
        <div className="flow-agent-chips">
          {Object.keys(node.agents).map((name) => (
            <span
              key={name}
              className="flow-agent-chip"
              data-agent={name}
              data-testid={`flow-agent-chip-${name}`}
            >
              {label(name)}
            </span>
          ))}
        </div>
      </div>
      <FlowSection title="输入" icon={ArrowDownToLine} collapsible={false}>
        <ul className="flow-path-list">
          {node.requires.length ? node.requires.map((r) => (
            <li key={r}><code className="flow-path-chip">{r}</code></li>
          )) : <li className="flow-empty">无</li>}
        </ul>
      </FlowSection>
      <FlowSection title="产出" icon={ArrowUpFromLine} collapsible={false}>
        <ul className="flow-path-list">
          {node.produces.map((p) => (
            <li key={p.path}>
              <code className="flow-path-chip">{p.path}</code>
            </li>
          ))}
        </ul>
      </FlowSection>
      <FlowSection title="注入规则" icon={ScrollText}>
        {globals.length ? (
          <>
            <h4>全局</h4>
            <ul className="flow-path-list">
              {globals.map((rule) => (
                <li key={rule.path}>
                  <button type="button" className="flow-rule-link" onClick={() => onPickRule(rule.path, rule.title)}>
                    {rulePathLabel(rule.path)}
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : null}
        {injected.length ? (
          <>
            <h4>本节点</h4>
            <ul className="flow-path-list">
              {injected.map((path) => (
                <li key={path}>
                  <button type="button" className="flow-rule-link" onClick={() => onPickRule(path)}>
                    {rulePathLabel(path)}
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : null}
        {Object.entries(node.agents).map(([name, agent]) => {
          const ownRules = agent.rules || [];
          return (
            <Fragment key={name}>
              <h4>{name}</h4>
              <ul className="flow-path-list">
                {ownRules.length ? ownRules.map((path) => (
                  <li key={path}>
                    <button type="button" className="flow-rule-link" onClick={() => onPickRule(path)}>
                      {rulePathLabel(path)}
                    </button>
                  </li>
                )) : <li className="flow-empty">无</li>}
              </ul>
            </Fragment>
          );
        })}
        {!globals.length && !injected.length && !Object.keys(node.agents).length ? (
          <ul className="flow-path-list">
            <li className="flow-empty">无</li>
          </ul>
        ) : null}
      </FlowSection>
    </section>
  );
}

function AgentDetail({ node, agentKey, models, onChange, note, globalRules, onPickRule }: {
  node: WorkflowNode; agentKey: string; models: ModelRow[];
  onChange: (node: string, agent: string, model: string, thinking: string) => Promise<void>;
  note: string;
  globalRules: WorkflowRuleCard[];
  onPickRule: (path: string, title?: string) => void;
}) {
  const agent = node.agents[agentKey];
  if (!agent) return null;
  const gm = agent.gui_model || "";
  const gt = agent.gui_thinking || "";
  const choices = modelChoices(models, gm).choices.filter((c) => c.value);
  const globals = globalRules || [];
  const injected = node.inject || [];
  const ownRules = agent.rules || [];
  const hasRules = globals.length > 0 || injected.length > 0 || ownRules.length > 0;
  return (
    <section className="flow-detail" data-testid={`flow-agent-detail-${node.id}-${agentKey}`}>
      <h3>{node.title || node.id} · {label(agentKey)}</h3>
      <p className="settings-meta">agent {agent.template || "内联"} · 当前模型 {agent.model}{agent.thinking ? ` · 思考 ${agent.thinking}` : ""}</p>
      <FlowSection title="模型" icon={Cpu} defaultOpen>
        <select className="flow-model" data-testid="agent-model-select" value={gm} onChange={(e) => void onChange(node.id, agentKey, e.target.value, gt)}>
          <option value="">使用默认模型</option>
          {choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <h4>思考</h4>
        <select className="flow-model" data-testid="agent-thinking-select" value={gt} onChange={(e) => void onChange(node.id, agentKey, gm, e.target.value)}>
          {THINKING_LEVELS.map((t) => <option key={t || "default"} value={t}>{t || "模型默认"}</option>)}
        </select>
        {note ? <p className="flow-model-note" data-testid="flow-model-note">{note}</p> : null}
      </FlowSection>
      <FlowSection title="权限" icon={Shield}>
        <h4>可读</h4>
        <ul className="flow-path-list">
          {agent.read.length ? agent.read.map((g) => <li key={g}><code className="flow-path-chip">{g}</code></li>) : <li className="flow-empty">无</li>}
        </ul>
        <h4>可写</h4>
        <ul className="flow-path-list">
          {agent.write.length ? agent.write.map((g) => <li key={g}><code className="flow-path-chip">{g}</code></li>) : <li className="flow-empty">无</li>}
        </ul>
      </FlowSection>
      <FlowSection title="工具" icon={Wrench}>
        <ul className="flow-plain-list">
          <li>文件工具{agentKey === "executor" ? "（含写入）" : "（只读）"}、submit</li>
          {agent.tools.mcp.length ? agent.tools.mcp.map((m) => <li key={m}>MCP：{m}</li>) : null}
          {agent.tools.skills.length ? agent.tools.skills.map((s) => <li key={s}>技能：{s}</li>) : null}
        </ul>
      </FlowSection>
      <FlowSection title="规则" icon={ScrollText}>
        {hasRules ? (
          <>
            {globals.length ? (
              <>
                <h4>全局</h4>
                <ul className="flow-path-list">
                  {globals.map((rule) => (
                    <li key={rule.path}>
                      <button type="button" className="flow-rule-link" onClick={() => onPickRule(rule.path, rule.title)}>
                        {rulePathLabel(rule.path)}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {injected.length ? (
              <>
                <h4>节点</h4>
                <ul className="flow-path-list">
                  {injected.map((path) => (
                    <li key={path}>
                      <button type="button" className="flow-rule-link" onClick={() => onPickRule(path)}>
                        {rulePathLabel(path)}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {ownRules.length ? (
              <>
                <h4>本代理</h4>
                <ul className="flow-path-list">
                  {ownRules.map((path) => (
                    <li key={path}>
                      <button type="button" className="flow-rule-link" onClick={() => onPickRule(path)}>
                        {rulePathLabel(path)}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </>
        ) : (
          <ul className="flow-path-list">
            <li className="flow-empty">无</li>
          </ul>
        )}
      </FlowSection>
    </section>
  );
}
