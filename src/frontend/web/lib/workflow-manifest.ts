import { translate } from "./i18n/messages";
import { uiLang } from "./run-status";
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
  if (!response.ok) throw new Error(data.detail || translate(uiLang(), "wf.listFail"));
  return data.workflows ?? [];
}
