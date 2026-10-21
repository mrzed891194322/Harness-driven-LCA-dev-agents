export type ResultKind = "work" | "intermediate" | "final" | "previous";
export type ArtifactCategory = "intermediate" | "deliverable" | "previous";

export const KIND_LABEL: Record<ResultKind, string> = {
  work: "工作记录",
  intermediate: "中间产物",
  final: "最终交付",
  previous: "上一版",
};

export function resultKind(filePath: string, category?: ArtifactCategory): ResultKind {
  if (category === "previous" || filePath.startsWith("workspace/artifacts/previous/")) return "previous";
  if (category === "deliverable") return "final";
  if (category === "intermediate") return "intermediate";
  if (filePath.startsWith("workspace/artifacts/")) return "final";
  if (filePath.startsWith("workspace/runs/_run/")) return "work";
  if (filePath.startsWith("workspace/runs/")) return "intermediate";
  return "work";
}

/** Labels for executor status and reviewer verdict in the 节点结论 list. */
export const VERDICT_LABEL: Record<string, string> = {
  ok: "完成",
  failed: "失败",
  blocked: "受阻",
  passed: "通过",
  accept: "通过",
  reject: "退回",
};

/** Header line for the current run, from the v5 manifest (current_node; old current_stage as fallback). */
export function runLine(manifest: { status?: string; current_node?: string | null; current_stage?: string | null; status_reason?: string | null } | undefined): string {
  if (!manifest?.status || manifest.status === "idle") return "";
  const node = manifest.current_node ?? manifest.current_stage;
  return [`状态 ${manifest.status}`, node ? `当前节点 ${node}` : "", manifest.status_reason || ""].filter(Boolean).join(" · ");
}
