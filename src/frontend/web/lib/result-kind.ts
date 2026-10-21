export type ResultKind = "work" | "intermediate" | "final" | "previous";
export type ArtifactCategory = "intermediate" | "deliverable" | "previous";

export const KIND_LABEL: Record<ResultKind, string> = {
  work: "工作记录",
  intermediate: "中间产物",
  final: "最终交付",
  previous: "上一版",
};

export function resultKind(filePath: string, category?: ArtifactCategory): ResultKind {
  // 上一版 tab is not in 599ed0a (needs Du Yuan approval): previous/ files show under 最终交付 with their previous/ path.
  if (category === "previous") return "final";
  if (category === "deliverable") return "final";
  if (category === "intermediate") return "intermediate";
  if (filePath.startsWith("workspace/artifacts/")) return "final";
  if (filePath.startsWith("workspace/runs/_run/")) return "work";
  if (filePath.startsWith("workspace/runs/")) return "intermediate";
  return "work";
}

/** Labels for executor status and reviewer verdict in the 节点结论 list (shared map). */
export { LABEL as VERDICT_LABEL } from "./labels.ts";
