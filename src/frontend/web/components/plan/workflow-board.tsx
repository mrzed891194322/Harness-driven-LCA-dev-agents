"use client";

import { Bot, ChevronLeft, ChevronRight, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  readSpec,
  readWorkflow,
  type AssignmentNode,
  type SpecSummary,
  type WorkflowGraph,
} from "./workflow-yaml";
import { apiFetch } from "../../lib/api";

const FILES = ["LCA-main.yaml", "LCA-revise.yaml"] as const;

const MODE_FILE = {
  new: "LCA-main.yaml",
  revise: "LCA-revise.yaml",
} as const;

export type WorkMode = keyof typeof MODE_FILE;

const FILE_LABEL: Record<string, string> = {
  "LCA-main.yaml": "主流程",
  "LCA-revise.yaml": "修订流程",
};

const STAGE_TITLE: Record<string, string> = {
  "01-intake-gate": "初始化检查",
  "02-inventory-extraction": "前景清单",
  "03-dataset-mapping": "数据集映射",
  "04-openlca-reporting": "计算与报告",
};

const ROLE_LABEL: Record<string, string> = {
  executor: "执行",
  reviewer: "审阅",
  reviser: "修订",
};

const PHASE_LABEL: Record<string, string> = {
  inventory: "清单",
  mapping: "映射",
  report: "报告",
};

type ModelOption = {
  id: string;
  label: string;
  provider: string;
  provider_name?: string;
  model_id: string;
};

function ModelOptions({ models }: { models: ModelOption[] }) {
  const groups: { name: string; items: ModelOption[] }[] = [];
  for (const item of models) {
    const name = item.provider_name || item.provider || "其他";
    const group = groups.find((entry) => entry.name === name);
    if (group) group.items.push(item);
    else groups.push({ name, items: [item] });
  }
  return groups.map((group) => (
    <optgroup key={group.name} label={group.name}>
      {group.items.map((item) => (
        <option key={item.id} value={item.id}>
          {item.label}
        </option>
      ))}
    </optgroup>
  ));
}

type Selection =
  | { kind: "workflow" }
  | { kind: "stage"; id: string }
  | { kind: "assignment"; id: string }
  | { kind: "rule"; id: string }
  | { kind: "mcp"; id: string }
  | { kind: "host"; id: string }
  | { kind: "knowledge"; id: string };

type Related = {
  stages: Set<string>;
  assignments: Set<string>;
  rules: Set<string>;
  mcp: Set<string>;
  host: Set<string>;
  knowledge: Set<string>;
};

function stageIdOf(assignmentId: string): string {
  const cut = assignmentId.lastIndexOf(".");
  return cut === -1 ? assignmentId : assignmentId.slice(0, cut);
}

function rulePath(workflow: WorkflowGraph, id: string): string {
  return workflow.rules.find((item) => item.id === id)?.path ?? id;
}

function assignmentOf(workflow: WorkflowGraph, id: string): AssignmentNode | undefined {
  return workflow.assignments.find((item) => item.id === id);
}

function remap(selection: Selection, workflow: WorkflowGraph): Selection {
  if (selection.kind === "workflow") return selection;
  if (selection.kind === "stage") {
    return workflow.stages.some((stage) => stage.id === selection.id) ? selection : { kind: "workflow" };
  }
  if (selection.kind === "assignment") {
    if (workflow.assignments.some((item) => item.id === selection.id)) return selection;
    const stageId = stageIdOf(selection.id);
    return workflow.stages.some((stage) => stage.id === stageId) ? { kind: "stage", id: stageId } : { kind: "workflow" };
  }
  if (selection.kind === "rule") {
    return workflow.rules.some((item) => item.id === selection.id) ? selection : { kind: "workflow" };
  }
  if (selection.kind === "mcp") {
    return workflow.mcp.some((item) => item.id === selection.id) ? selection : { kind: "workflow" };
  }
  if (selection.kind === "host") {
    return workflow.hostActions.some((item) => item.id === selection.id) ? selection : { kind: "workflow" };
  }
  return workflow.knowledge.some((item) => item.id === selection.id) ? selection : { kind: "workflow" };
}

function relatedOf(workflow: WorkflowGraph, selection: Selection, specs: Record<string, SpecSummary>): Related {
  const related: Related = {
    stages: new Set(),
    assignments: new Set(),
    rules: new Set(),
    mcp: new Set(),
    host: new Set(),
    knowledge: new Set(),
  };
  const stageActions = (stageId: string) => {
    const stage = workflow.stages.find((item) => item.id === stageId);
    const spec = stage ? specs[stage.spec] : undefined;
    return [...(spec?.checks ?? []), ...(spec?.afterPass ?? [])];
  };
  if (selection.kind === "stage") {
    const stage = workflow.stages.find((item) => item.id === selection.id);
    stage?.rules.forEach((id) => related.rules.add(id));
    stage?.steps.forEach((step) => related.assignments.add(step.assignment));
    stageActions(selection.id).forEach((item) => related.host.add(item.action));
  } else if (selection.kind === "assignment") {
    related.stages.add(stageIdOf(selection.id));
    const assignment = assignmentOf(workflow, selection.id);
    assignment?.rules.forEach((id) => related.rules.add(id));
    assignment?.mcp.forEach((id) => related.mcp.add(id));
  } else if (selection.kind === "rule") {
    for (const stage of workflow.stages) {
      if (stage.rules.includes(selection.id)) related.stages.add(stage.id);
    }
    for (const assignment of workflow.assignments) {
      if (assignment.rules.includes(selection.id)) {
        related.assignments.add(assignment.id);
        related.stages.add(stageIdOf(assignment.id));
      }
    }
    for (const tool of workflow.mcp) {
      if (tool.rules.includes(selection.id)) related.mcp.add(tool.id);
    }
  } else if (selection.kind === "mcp") {
    for (const assignment of workflow.assignments) {
      if (assignment.mcp.includes(selection.id)) {
        related.assignments.add(assignment.id);
        related.stages.add(stageIdOf(assignment.id));
      }
    }
  } else if (selection.kind === "host") {
    for (const stage of workflow.stages) {
      if (stageActions(stage.id).some((item) => item.action === selection.id)) related.stages.add(stage.id);
    }
  }
  return related;
}

async function fetchDoc(path: string): Promise<string> {
  const response = await apiFetch(`/api/harness/document?path=${encodeURIComponent(path)}`);
  const data = (await response.json()) as { content?: string; detail?: string };
  if (!response.ok || !data.content) throw new Error(data.detail || "无法读取编排");
  return data.content;
}

function harnessPath(path: string): string {
  return path.startsWith("harness/") ? path.slice("harness/".length) : path;
}

let cachedWorkflows: WorkflowGraph[] | null = null;
let cachedSpecs: Record<string, SpecSummary> | null = null;

export function WorkflowBoard({ mode }: { mode: WorkMode }) {
  const [workflows, setWorkflows] = useState<WorkflowGraph[]>(cachedWorkflows ?? []);
  const [specs, setSpecs] = useState<Record<string, SpecSummary>>(cachedSpecs ?? {});
  const [selection, setSelection] = useState<Selection>({ kind: "workflow" });
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [error, setError] = useState("");
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [defaultModel, setDefaultModel] = useState("");
  const [assignmentModels, setAssignmentModels] = useState<Record<string, string>>({});
  const [modelNote, setModelNote] = useState("");
  const [assignmentNote, setAssignmentNote] = useState("");
  const file = MODE_FILE[mode];

  useEffect(() => {
    if (cachedWorkflows) {
      setWorkflows(cachedWorkflows);
      setSpecs(cachedSpecs ?? {});
      return;
    }
    let cancelled = false;
    Promise.all(FILES.map(async (name) => readWorkflow(await fetchDoc(name), name)))
      .then(async (loaded) => {
        if (cancelled) return;
        cachedWorkflows = loaded;
        setWorkflows(loaded);
        const specPaths = [...new Set(loaded.flatMap((item) => item.stages.map((stage) => stage.spec)))];
        const entries = await Promise.all(
          specPaths.map(async (specPath) => {
            try {
              return [specPath, readSpec(await fetchDoc(harnessPath(specPath)))] as const;
            } catch {
              return null;
            }
          }),
        );
        if (cancelled) return;
        const nextSpecs = Object.fromEntries(entries.filter((item) => item !== null));
        cachedSpecs = nextSpecs;
        setSpecs(nextSpecs);
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : "无法读取编排");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiFetch("/api/workflow/models")
      .then(async (response) => {
        const data = (await response.json()) as {
          default?: string;
          default_ref?: string;
          assignments?: Record<string, string>;
          models?: ModelOption[];
          detail?: string;
        };
        if (!response.ok) throw new Error(data.detail || "无法读取模型");
        return data;
      })
      .then((data) => {
        if (cancelled) return;
        setModels(data.models ?? []);
        setDefaultModel(data.default_ref || data.default || "");
        setAssignmentModels(data.assignments ?? {});
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setModelNote(reason instanceof Error ? reason.message : "无法读取模型");
      })
      .finally(() => {
        if (!cancelled) setModelsLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const workflow = workflows.find((item) => item.file === file) ?? workflows[0];
  const other = workflows.find((item) => item !== workflow);
  const related = useMemo(
    () => (workflow ? relatedOf(workflow, selection, specs) : null),
    [workflow, selection, specs],
  );

  useEffect(() => {
    if (!workflow) return;
    setSelection((current) => remap(current, workflow));
  }, [workflow]);

  if (error) {
    return (
      <div className="flow-board">
        <p className="status-banner error">{error}</p>
      </div>
    );
  }
  if (!workflow || !related) {
    return (
      <div className="flow-board">
        <p className="flow-loading">正在读取编排…</p>
      </div>
    );
  }

  function choose(next: Selection) {
    setSelection(next);
    setInspectorOpen(true);
  }

  function openGlobal() {
    setSelection({ kind: "workflow" });
    setInspectorOpen(true);
  }

  const defaultLabel = models.find((item) => item.id === defaultModel)?.label ?? defaultModel;

  async function changeDefault(profileId: string) {
    const previous = defaultModel;
    setDefaultModel(profileId);
    setModelNote("");
    const response = await apiFetch("/api/models/selection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId }),
    });
    if (!response.ok) {
      const data = (await response.json().catch(() => ({}))) as { detail?: string };
      setDefaultModel(previous);
      setModelNote(data.detail || "默认模型没有保存");
    }
  }

  async function changeAssignment(assignmentId: string, profileId: string) {
    const previous = assignmentModels;
    const next = { ...assignmentModels };
    if (profileId) next[assignmentId] = profileId;
    else delete next[assignmentId];
    setAssignmentModels(next);
    setAssignmentNote("");
    const response = await apiFetch("/api/workflow/models", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assignments: next }),
    });
    if (!response.ok) {
      const data = (await response.json().catch(() => ({}))) as { detail?: string };
      setAssignmentModels(previous);
      setAssignmentNote(data.detail || "分工模型没有保存");
    }
  }

  return (
    <div className="flow-board" data-inspector={inspectorOpen ? "true" : "false"}>
      <div className="flow-toolbar">
        <button type="button" className="flow-config" onClick={openGlobal}>
          <SlidersHorizontal size={16} strokeWidth={1.75} aria-hidden="true" />
          配置面板
        </button>
      </div>

      <div className="flow-stages">
        {workflow.stages.map((stage, index) => {
          const active = selection.kind === "stage" && selection.id === stage.id;
          return (
            <div className="flow-stage-wrap" key={stage.id}>
              {index > 0 ? (
                <div className="flow-arrow" aria-hidden="true">
                  <ChevronRight size={16} />
                </div>
              ) : null}
              <article
                className="flow-stage"
                data-active={active ? "true" : "false"}
                data-related={!active && related.stages.has(stage.id) ? "true" : "false"}
                onClick={() => choose({ kind: "stage", id: stage.id })}
              >
                <button
                  type="button"
                  className="flow-stage-head"
                  aria-pressed={active}
                  onClick={(event) => {
                    event.stopPropagation();
                    choose({ kind: "stage", id: stage.id });
                  }}
                >
                  <span className="flow-stage-index">{stage.id.slice(0, 2)}</span>
                  <strong>{STAGE_TITLE[stage.id] ?? stage.id}</strong>
                  <small>
                    最多 {stage.maxAttempts} 次
                    {stage.phase ? ` · ${PHASE_LABEL[stage.phase] ?? stage.phase}` : ""}
                  </small>
                </button>
                <div
                  className="flow-steps"
                  onClick={(event) => event.stopPropagation()}
                >
                  {stage.steps.map((step) => {
                    const assignment = assignmentOf(workflow, step.assignment);
                    const role = assignment?.role ?? "";
                    const chosen = assignmentModels[step.assignment] ?? "";
                    const roleLabel = ROLE_LABEL[role] ?? role;
                    return (
                      <button
                        key={step.assignment}
                        type="button"
                        className="flow-step"
                        data-role={role}
                        data-related={related.assignments.has(step.assignment) ? "true" : "false"}
                        aria-pressed={selection.kind === "assignment" && selection.id === step.assignment}
                        onClick={() => choose({ kind: "assignment", id: step.assignment })}
                      >
                        <span className="flow-step-role">
                          <Bot className="flow-step-icon" size={15} strokeWidth={1.75} aria-hidden="true" />
                          <em>{roleLabel}</em>
                        </span>
                        <small>
                            {chosen
                              ? models.find((item) => item.id === chosen)?.label ?? chosen
                              : defaultLabel
                                ? `默认 · ${defaultLabel}`
                                : "默认"}
                          </small>
                      </button>
                    );
                  })}
                </div>
              </article>
            </div>
          );
        })}
      </div>

      {inspectorOpen ? (
        <Inspector
          workflow={workflow}
          other={other}
          specs={specs}
          selection={selection}
          models={models}
          modelsLoaded={modelsLoaded}
          defaultModel={defaultModel}
          assignmentModels={assignmentModels}
          modelNote={modelNote}
          assignmentNote={assignmentNote}
          onSelect={choose}
          onClose={() => setInspectorOpen(false)}
          onChangeDefault={(profileId) => void changeDefault(profileId)}
          onChangeAssignment={(assignmentId, profileId) => void changeAssignment(assignmentId, profileId)}
        />
      ) : null}
    </div>
  );
}

function Inspector({
  workflow,
  other,
  specs,
  selection,
  models,
  modelsLoaded,
  defaultModel,
  assignmentModels,
  modelNote,
  assignmentNote,
  onSelect,
  onClose,
  onChangeDefault,
  onChangeAssignment,
}: {
  workflow: WorkflowGraph;
  other?: WorkflowGraph;
  specs: Record<string, SpecSummary>;
  selection: Selection;
  models: ModelOption[];
  modelsLoaded: boolean;
  defaultModel: string;
  assignmentModels: Record<string, string>;
  modelNote: string;
  assignmentNote: string;
  onSelect: (selection: Selection) => void;
  onClose: () => void;
  onChangeDefault: (profileId: string) => void;
  onChangeAssignment: (assignmentId: string, profileId: string) => void;
}) {
  return (
    <aside className="flow-inspector" aria-live="polite">
      {selection.kind !== "workflow" ? (
        <button type="button" className="flow-back" onClick={() => onSelect({ kind: "workflow" })}>
          <ChevronLeft size={16} strokeWidth={1.75} aria-hidden="true" />
          回到全局规则
        </button>
      ) : null}
      <button type="button" className="flow-close" aria-label="关闭" onClick={onClose}>
        <X size={16} strokeWidth={1.75} aria-hidden="true" />
      </button>
      {selection.kind === "workflow" ? (
        <GlobalRules
          workflow={workflow}
          models={models}
          modelsLoaded={modelsLoaded}
          defaultModel={defaultModel}
          modelNote={modelNote}
          onSelect={onSelect}
          onChangeDefault={onChangeDefault}
        />
      ) : null}
      {selection.kind === "stage" ? (
        <StageDetail
          workflow={workflow}
          other={other}
          stageId={selection.id}
          specs={specs}
          onSelect={onSelect}
        />
      ) : null}
      {selection.kind === "assignment" ? (
        <AssignmentDetail
          workflow={workflow}
          assignmentId={selection.id}
          models={models}
          defaultModel={defaultModel}
          chosen={assignmentModels[selection.id] ?? ""}
          modelNote={assignmentNote}
          onSelect={onSelect}
          onChangeModel={(profileId) => onChangeAssignment(selection.id, profileId)}
        />
      ) : null}
      {selection.kind === "rule" ? <RuleDetail workflow={workflow} ruleId={selection.id} onSelect={onSelect} /> : null}
      {selection.kind === "mcp" ? <McpDetail workflow={workflow} toolId={selection.id} onSelect={onSelect} /> : null}
      {selection.kind === "host" ? (
        <HostDetail workflow={workflow} specs={specs} actionId={selection.id} onSelect={onSelect} />
      ) : null}
      {selection.kind === "knowledge" ? <KnowledgeDetail workflow={workflow} knowledgeId={selection.id} /> : null}
    </aside>
  );
}

function Kicker({ children }: { children: string }) {
  return <p className="flow-kicker">{children}</p>;
}

function JumpList({
  label,
  items,
  pressedId,
  onPick,
}: {
  label: string;
  items: { id: string; text: string; title?: string }[];
  pressedId?: string;
  onPick: (id: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="flow-block">
      <h3>{label}</h3>
      <div className="flow-links">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className="flow-jump"
            title={item.title}
            aria-pressed={pressedId === item.id}
            onClick={() => onPick(item.id)}
          >
            {item.text}
          </button>
        ))}
      </div>
    </div>
  );
}

function GlobalRules({
  workflow,
  models,
  modelsLoaded,
  defaultModel,
  modelNote,
  onSelect,
  onChangeDefault,
}: {
  workflow: WorkflowGraph;
  models: ModelOption[];
  modelsLoaded: boolean;
  defaultModel: string;
  modelNote: string;
  onSelect: (selection: Selection) => void;
  onChangeDefault: (profileId: string) => void;
}) {
  return (
    <>
      <Kicker>编排</Kicker>
      <h3>全局规则</h3>
      <p className="flow-lead">对所有阶段生效。没有单独指定模型的分工使用这里的默认模型。</p>
      <JumpList
        label="规则"
        items={workflow.defaults.rules.map((id) => ({ id, text: id, title: rulePath(workflow, id) }))}
        onPick={(id) => onSelect({ kind: "rule", id })}
      />
      <JumpList
        label="工具"
        items={[
          ...workflow.mcp.map((tool) => ({ id: tool.id, text: `MCP · ${tool.id}` })),
          ...workflow.hostActions.map((action) => ({ id: action.id, text: `检查 · ${action.id}` })),
        ]}
        onPick={(id) => {
          const tool = workflow.mcp.some((item) => item.id === id);
          onSelect(tool ? { kind: "mcp", id } : { kind: "host", id });
        }}
      />
      <JumpList
        label="知识"
        items={workflow.defaults.knowledge.map((id) => ({ id, text: id }))}
        onPick={(id) => onSelect({ kind: "knowledge", id })}
      />
      <div className="flow-block">
        <h3>默认模型</h3>
        <select
          className="flow-model"
          aria-label="默认模型"
          value={models.some((item) => item.id === defaultModel) ? defaultModel : ""}
          disabled={!models.length}
          onChange={(event) => onChangeDefault(event.target.value)}
        >
          {!models.length ? (
            <option value="">{modelsLoaded ? "尚未连接模型" : "正在读取已连接模型…"}</option>
          ) : null}
          <ModelOptions models={models} />
        </select>
        {modelNote ? <p className="flow-model-note">{modelNote}</p> : null}
      </div>
    </>
  );
}

function StageDetail({
  workflow,
  other,
  stageId,
  specs,
  onSelect,
}: {
  workflow: WorkflowGraph;
  other?: WorkflowGraph;
  stageId: string;
  specs: Record<string, SpecSummary>;
  onSelect: (selection: Selection) => void;
}) {
  const stage = workflow.stages.find((item) => item.id === stageId);
  if (!stage) return null;
  const spec = specs[stage.spec];
  const otherStage = other?.stages.find((item) => item.id === stage.id);
  const otherLabel = other ? FILE_LABEL[other.file] ?? other.id : "";
  const extraRules = otherStage ? otherStage.rules.filter((id) => !stage.rules.includes(id)) : [];
  return (
    <>
      <Kicker>阶段</Kicker>
      <h3>{STAGE_TITLE[stage.id] ?? stage.id}</h3>
      <p className="flow-lead">{stage.id}</p>
      <dl className="flow-facts">
        <div>
          <dt>次数上限</dt>
          <dd>{stage.maxAttempts}</dd>
        </div>
        {stage.phase ? (
          <div>
            <dt>上下文</dt>
            <dd>{PHASE_LABEL[stage.phase] ?? stage.phase}</dd>
          </div>
        ) : null}
        <div>
          <dt>规格</dt>
          <dd>{stage.spec}</dd>
        </div>
      </dl>
      <JumpList
        label="分工"
        items={stage.steps.map((step) => {
          const role = assignmentOf(workflow, step.assignment)?.role ?? "";
          return { id: step.assignment, text: `${ROLE_LABEL[role] ?? role} · ${step.assignment}` };
        })}
        onPick={(id) => onSelect({ kind: "assignment", id })}
      />
      <JumpList
        label="附加规则"
        items={stage.rules.map((id) => ({ id, text: id, title: rulePath(workflow, id) }))}
        onPick={(id) => onSelect({ kind: "rule", id })}
      />
      {other && otherStage && extraRules.length ? (
        <PathList label={`${otherLabel}另外附带`} paths={extraRules} />
      ) : null}
      {spec ? (
        <>
          <PathList label="输入" paths={spec.inputs.map((item) => item.path)} />
          <PathList label="输出" paths={spec.outputs.map((item) => item.path)} />
          <JumpList
            label="验收"
            items={spec.checks.map((item) => ({ id: item.action, text: `${item.id} · ${item.action}` }))}
            onPick={(id) => onSelect({ kind: "host", id })}
          />
          <JumpList
            label="通过后"
            items={spec.afterPass.map((item) => ({ id: item.action, text: `${item.id} · ${item.action}` }))}
            onPick={(id) => onSelect({ kind: "host", id })}
          />
        </>
      ) : null}
    </>
  );
}

function AssignmentDetail({
  workflow,
  assignmentId,
  models,
  defaultModel,
  chosen,
  modelNote,
  onSelect,
  onChangeModel,
}: {
  workflow: WorkflowGraph;
  assignmentId: string;
  models: ModelOption[];
  defaultModel: string;
  chosen: string;
  modelNote: string;
  onSelect: (selection: Selection) => void;
  onChangeModel: (profileId: string) => void;
}) {
  const assignment = assignmentOf(workflow, assignmentId);
  if (!assignment) return null;
  const stageId = stageIdOf(assignment.id);
  const defaultLabel = models.find((item) => item.id === defaultModel)?.label ?? defaultModel;
  return (
    <>
      <Kicker>分工</Kicker>
      <h3>{ROLE_LABEL[assignment.role] ?? assignment.role}</h3>
      <p className="flow-lead">{assignment.id}</p>
      <div className="flow-block">
        <h3>模型</h3>
        <select
          className="flow-model"
          aria-label="分工模型"
          value={chosen}
          disabled={!models.length}
          onChange={(event) => onChangeModel(event.target.value)}
        >
          <option value="">{defaultLabel ? `默认 · ${defaultLabel}` : "默认"}</option>
          <ModelOptions models={models} />
          {chosen && !models.some((item) => item.id === chosen) ? <option value={chosen}>{chosen}</option> : null}
        </select>
        {modelNote ? <p className="flow-model-note">{modelNote}</p> : null}
      </div>
      <JumpList
        label="所在阶段"
        items={[{ id: stageId, text: STAGE_TITLE[stageId] ?? stageId }]}
        onPick={(id) => onSelect({ kind: "stage", id })}
      />
      <JumpList
        label="MCP"
        items={assignment.mcp.map((id) => ({ id, text: id }))}
        onPick={(id) => onSelect({ kind: "mcp", id })}
      />
      <JumpList
        label="规则"
        items={assignment.rules.map((id) => ({ id, text: id, title: rulePath(workflow, id) }))}
        onPick={(id) => onSelect({ kind: "rule", id })}
      />
    </>
  );
}

function RuleDetail({
  workflow,
  ruleId,
  onSelect,
}: {
  workflow: WorkflowGraph;
  ruleId: string;
  onSelect: (selection: Selection) => void;
}) {
  const stages = workflow.stages.filter((stage) => stage.rules.includes(ruleId));
  const assignments = workflow.assignments.filter((item) => item.rules.includes(ruleId));
  const tools = workflow.mcp.filter((tool) => tool.rules.includes(ruleId));
  const inDefaults = workflow.defaults.rules.includes(ruleId);
  return (
    <>
      <Kicker>规则</Kicker>
      <h3>{ruleId}</h3>
      <p className="flow-lead">{rulePath(workflow, ruleId)}</p>
      {inDefaults ? <p className="flow-note">每个阶段都会附带这条规则。</p> : null}
      <JumpList
        label="阶段附加"
        items={stages.map((stage) => ({ id: stage.id, text: STAGE_TITLE[stage.id] ?? stage.id }))}
        onPick={(id) => onSelect({ kind: "stage", id })}
      />
      <JumpList
        label="分工附加"
        items={assignments.map((item) => ({
          id: item.id,
          text: `${ROLE_LABEL[item.role] ?? item.role} · ${item.id}`,
        }))}
        onPick={(id) => onSelect({ kind: "assignment", id })}
      />
      <JumpList
        label="绑定工具"
        items={tools.map((tool) => ({ id: tool.id, text: tool.id }))}
        onPick={(id) => onSelect({ kind: "mcp", id })}
      />
    </>
  );
}

function McpDetail({
  workflow,
  toolId,
  onSelect,
}: {
  workflow: WorkflowGraph;
  toolId: string;
  onSelect: (selection: Selection) => void;
}) {
  const tool = workflow.mcp.find((item) => item.id === toolId);
  if (!tool) return null;
  const users = workflow.assignments.filter((item) => item.mcp.includes(tool.id));
  return (
    <>
      <Kicker>MCP</Kicker>
      <h3>{tool.id}</h3>
      <p className="flow-lead">{tool.transport}</p>
      <pre className="flow-code">{[tool.command, ...tool.args].join(" ")}</pre>
      {tool.toolTimeoutSec ? <p className="flow-note">超时 {tool.toolTimeoutSec} 秒</p> : null}
      <JumpList
        label="使用这条工具的分工"
        items={users.map((item) => ({
          id: item.id,
          text: `${ROLE_LABEL[item.role] ?? item.role} · ${item.id}`,
        }))}
        onPick={(id) => onSelect({ kind: "assignment", id })}
      />
      <JumpList
        label="工具规则"
        items={tool.rules.map((id) => ({ id, text: id, title: rulePath(workflow, id) }))}
        onPick={(id) => onSelect({ kind: "rule", id })}
      />
    </>
  );
}

function HostDetail({
  workflow,
  specs,
  actionId,
  onSelect,
}: {
  workflow: WorkflowGraph;
  specs: Record<string, SpecSummary>;
  actionId: string;
  onSelect: (selection: Selection) => void;
}) {
  const action = workflow.hostActions.find((item) => item.id === actionId);
  if (!action) return null;
  const stages = workflow.stages.filter((stage) => {
    const spec = specs[stage.spec];
    return [...(spec?.checks ?? []), ...(spec?.afterPass ?? [])].some((item) => item.action === action.id);
  });
  return (
    <>
      <Kicker>宿主动作</Kicker>
      <h3>{action.id}</h3>
      <pre className="flow-code">{[action.command, ...action.args].join(" ")}</pre>
      {action.timeoutSec ? <p className="flow-note">超时 {action.timeoutSec} 秒</p> : null}
      <JumpList
        label="触发阶段"
        items={stages.map((stage) => ({ id: stage.id, text: STAGE_TITLE[stage.id] ?? stage.id }))}
        onPick={(id) => onSelect({ kind: "stage", id })}
      />
    </>
  );
}

function KnowledgeDetail({ workflow, knowledgeId }: { workflow: WorkflowGraph; knowledgeId: string }) {
  const source = workflow.knowledge.find((item) => item.id === knowledgeId);
  if (!source) return null;
  return (
    <>
      <Kicker>知识</Kicker>
      <h3>{source.id}</h3>
      <dl className="flow-facts">
        <div>
          <dt>类型</dt>
          <dd>{source.kind}</dd>
        </div>
        <div>
          <dt>来源</dt>
          <dd>{source.provider}</dd>
        </div>
        <div>
          <dt>路径</dt>
          <dd>{source.path}</dd>
        </div>
      </dl>
      {workflow.defaults.knowledge.includes(source.id) ? <p className="flow-note">默认附带到每个阶段。</p> : null}
    </>
  );
}

function PathList({ label, paths }: { label: string; paths: string[] }) {
  if (!paths.length) return null;
  return (
    <div className="flow-block">
      <h3>{label}</h3>
      <ul className="flow-paths">
        {paths.map((path) => (
          <li key={path}>{path}</li>
        ))}
      </ul>
    </div>
  );
}
