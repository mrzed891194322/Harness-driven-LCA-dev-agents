/** v5 workflow cards from /api/v5/workflows, shared by /plan boards. */
export type V5Agent = {
  template: string; // agent template name (harness/workflows/agents/<name>.yaml); "" = inline
  model: string;
  thinking: string;
  model_source?: string;
  gui_model?: string;
  gui_thinking?: string;
  tools: { mcp: string[]; skills: string[] };
  rules: string[];
  read: string[];
  write: string[];
};
export type V5Node = {
  id: string;
  title: string;
  requires: string[];
  produces: { spec: string; path: string }[];
  max_rounds: number;
  agents: Record<string, V5Agent>;
};
export type V5Workflow = { id: string; title?: string; plan_file: string; revise_of?: string | null; nodes: string[]; details: V5Node[] };

export const THINKING_LEVELS = ["", "off", "minimal", "low", "medium", "high", "xhigh"];

/** 新工作 -> full-lca (or the first non-revise workflow); 修改工作 -> the workflow with revise_of. */
export function workflowForMode(list: V5Workflow[], mode: "new" | "revise"): V5Workflow | undefined {
  if (mode === "revise") return list.find((w) => w.revise_of) || list.find((w) => w.id === "revise-lca");
  return list.find((w) => w.id === "full-lca") || list.find((w) => !w.revise_of && !w.id.startsWith("demo"));
}
