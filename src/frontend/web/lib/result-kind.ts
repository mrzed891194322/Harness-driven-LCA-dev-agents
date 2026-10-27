import { translate } from "./i18n/messages";
import { uiLang } from "./run-status";

/** Results sidebar: 工作记录 | 最终交付 (no 中间产物 tab). */
export type ResultKind = "work" | "final";
/** Backend artifact category; ``work``/``intermediate`` both map to 工作记录. */
export type ArtifactCategory = "intermediate" | "deliverable" | "work";

const KIND_KEYS: Record<ResultKind, string> = {
  work: "results.kindWork",
  final: "results.kindFinal",
};

/** Sidebar tab order. */
export const RESULT_KINDS: ResultKind[] = ["work", "final"];

/** @deprecated prefer kindLabel(); kept for call sites expecting a map */
export const KIND_LABEL: Record<ResultKind, string> = {
  get work() { return kindLabel("work"); },
  get final() { return kindLabel("final"); },
};

export function kindLabel(kind: ResultKind): string {
  return translate(uiLang(), KIND_KEYS[kind]);
}

/** 最终交付：仅 BOM / LCI(mapping) / 报告三类。 */
const FINAL_PREFIXES = [
  "workspace/artifacts/bom/",
  "workspace/artifacts/mapping/",
  "workspace/artifacts/report/",
  "workspace/artifacts/LCI/",
];

const FINAL_BASENAMES = new Set([
  "extracted-bom.json",
  "extracted-bom.md",
  "lca_report.md",
  "human_readable_mapping.md",
]);

function baseName(filePath: string): string {
  const parts = filePath.split("/");
  return parts[parts.length - 1] || filePath;
}

export function isFinalDeliverablePath(filePath: string): boolean {
  if (FINAL_PREFIXES.some((prefix) => filePath.startsWith(prefix))) return true;
  if (filePath.startsWith("workspace/artifacts/") && FINAL_BASENAMES.has(baseName(filePath))) {
    return true;
  }
  return false;
}

export function resultKind(filePath: string, category?: ArtifactCategory): ResultKind {
  if (isFinalDeliverablePath(filePath)) return "final";
  // Explicit non-final categories stay in 工作记录 even if under artifacts/.
  if (category === "deliverable" && filePath.startsWith("workspace/artifacts/")) {
    // deliverable but not BOM/LCI/report → work (e.g. calculation-plan.json)
    return "work";
  }
  return "work";
}

/** Labels for executor status and reviewer verdict in the 节点结论 list (shared map). */
export { LABEL as VERDICT_LABEL } from "./labels.ts";
