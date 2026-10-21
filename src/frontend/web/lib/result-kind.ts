export type ResultKind = "work" | "intermediate" | "final";
export type ArtifactCategory = "intermediate" | "deliverable";

export const KIND_LABEL: Record<ResultKind, string> = {
  work: "工作记录",
  intermediate: "中间产物",
  final: "最终交付",
};

export function resultKind(filePath: string, category?: ArtifactCategory): ResultKind {
  if (category === "deliverable") return "final";
  if (category === "intermediate") return "intermediate";
  if (filePath.startsWith("workspace/artifacts/")) return "final";
  if (filePath.startsWith("workspace/runs/_run/")) return "work";
  if (filePath.startsWith("workspace/runs/")) return "intermediate";
  return "work";
}

/** Labels for executor status and reviewer verdict in the 节点结论 list (shared map). */
export { LABEL as VERDICT_LABEL } from "./labels.ts";
