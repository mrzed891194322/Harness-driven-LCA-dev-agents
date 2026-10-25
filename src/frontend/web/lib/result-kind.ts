import { translate } from "./i18n/messages";
import { uiLang } from "./run-status";

export type ResultKind = "work" | "intermediate" | "final";
export type ArtifactCategory = "intermediate" | "deliverable";

const KIND_KEYS: Record<ResultKind, string> = {
  work: "results.kindWork",
  intermediate: "results.kindIntermediate",
  final: "results.kindFinal",
};

/** @deprecated prefer kindLabel(); kept for call sites expecting a map */
export const KIND_LABEL: Record<ResultKind, string> = {
  get work() { return kindLabel("work"); },
  get intermediate() { return kindLabel("intermediate"); },
  get final() { return kindLabel("final"); },
};

export function kindLabel(kind: ResultKind): string {
  return translate(uiLang(), KIND_KEYS[kind]);
}

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
