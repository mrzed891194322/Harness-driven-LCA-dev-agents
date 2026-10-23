/** workflow cards from /api/workflow/workflows, shared by /plan boards. */
export type WorkflowAgent = {
  template: string; // agent template name (harness/workflows/agents/<name>.yaml); "" = inline
  model: string;
  thinking: string;
  model_source?: string;
  gui_model?: string;
  gui_thinking?: string;
  /** deliver.submit after template resolve: artifact = 主 agent (§8), verdict = reviewer */
  submit?: "artifact" | "verdict";
  tools: { mcp: string[]; skills: string[] };
  rules: string[];
  read: string[];
  write: string[];
};
export type WorkflowFlowEdge = {
  from: string;
  when?: string | null;
  to: string;
  max?: number;
};

export type WorkflowFlow = {
  start: string;
  edges: WorkflowFlowEdge[];
};

export type WorkflowRuleCard = {
  id: string;
  title: string;
  path: string;
  enabled?: boolean;
  applies_to?: string[] | null;
};

export type WorkflowNode = {
  id: string;
  title: string;
  requires: string[];
  produces: { spec: string; path: string }[];
  /** Node-level inject rules (harness-relative paths), same as Injector step with agent.rules */
  inject?: string[];
  max_rounds: number;
  flow?: WorkflowFlow;
  agents: Record<string, WorkflowAgent>;
};
export type WorkflowCard = {
  id: string;
  title?: string;
  plan_file: string;
  start_rev?: "zero" | "next";
  max_redos?: number;
  nodes: string[];
  /** Global harness/rules/global/*.yaml (Injector step 1) */
  global_rules?: WorkflowRuleCard[];
  details: WorkflowNode[];
};

export const THINKING_LEVELS = ["", "off", "minimal", "low", "medium", "high", "xhigh"];

/** 新工作 -> full-lca (or the first non-revise workflow); 修改工作 -> the workflow with start_rev: next. */
export function workflowForMode(list: WorkflowCard[], mode: "new" | "revise"): WorkflowCard | undefined {
  if (mode === "revise") return list.find((w) => w.start_rev === "next") || list.find((w) => w.id === "revise-lca");
  return list.find((w) => w.id === "full-lca") || list.find((w) => w.start_rev !== "next" && !w.id.startsWith("demo"));
}
