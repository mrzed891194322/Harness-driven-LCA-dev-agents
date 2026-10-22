import { apiFetch } from "./api";

export type WorkflowListItem = {
  name: string;
  id: string;
  title: string;
  mode: string;
  file: string;
};

export async function fetchWorkflowList(): Promise<WorkflowListItem[]> {
  const response = await apiFetch("/api/workflows");
  const data = (await response.json()) as { workflows?: WorkflowListItem[]; detail?: string };
  if (!response.ok) throw new Error(data.detail || "无法读取工作流列表");
  return data.workflows ?? [];
}
