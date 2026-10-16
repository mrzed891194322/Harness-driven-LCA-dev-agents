import { apiFetch } from "./api";

export type WorkflowListItem = {
  name: string;
  title: string;
  mode: string;
  file: string;
};

export type ManifestAssignment = {
  id: string;
  role: string;
  title: string;
};

export type ManifestStage = {
  id: string;
  title: string;
  short_title: string;
  resumable: boolean;
  phase_title: string;
  assignments: ManifestAssignment[];
};

export type WorkflowManifest = {
  name: string;
  title: string;
  mode: string;
  plan: string;
  stages: ManifestStage[];
};

export function harnessWorkflowDocPath(file: string): string {
  const normalized = file.replace(/^harness\//, "");
  return normalized.startsWith("workflows/") ? normalized : `workflows/${normalized}`;
}

export async function fetchWorkflowList(): Promise<WorkflowListItem[]> {
  const response = await apiFetch("/api/workflows");
  const data = (await response.json()) as { workflows?: WorkflowListItem[]; detail?: string };
  if (!response.ok) throw new Error(data.detail || "无法读取工作流列表");
  return data.workflows ?? [];
}

export async function fetchWorkflowManifest(name: string): Promise<WorkflowManifest> {
  const response = await apiFetch(`/api/workflows/${encodeURIComponent(name)}/manifest`);
  const data = (await response.json()) as WorkflowManifest & { detail?: string };
  if (!response.ok) throw new Error(data.detail || "无法读取工作流清单");
  return data;
}

export function workflowNameForMode(
  list: WorkflowListItem[],
  mode: "new" | "revise",
): string {
  const want = mode === "revise" ? "revise" : "main";
  const hit = list.find((item) => item.mode === want);
  if (hit) return hit.name;
  return mode === "revise" ? "LCA-revise" : "LCA-main";
}

export function stageTitle(manifest: WorkflowManifest | null, stageId: string): string {
  if (!manifest) return stageId;
  return manifest.stages.find((stage) => stage.id === stageId)?.title ?? stageId;
}

export function assignmentTitle(
  manifest: WorkflowManifest | null,
  assignmentId: string,
  role?: string,
): string {
  if (!manifest) return role || assignmentId;
  for (const stage of manifest.stages) {
    const item = stage.assignments.find((row) => row.id === assignmentId);
    if (item) return item.title || item.role;
  }
  return role || assignmentId;
}

export function resumableStageIds(manifest: WorkflowManifest | null): string[] {
  if (!manifest) return [];
  return manifest.stages.filter((stage) => stage.resumable).map((stage) => stage.id);
}
