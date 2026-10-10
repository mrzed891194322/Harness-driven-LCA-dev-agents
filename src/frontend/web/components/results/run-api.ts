import { apiFetch } from "../../lib/api";

export type DiffItem = {
  item: string;
  level: "ok" | "warn" | "mismatch";
  kind: string;
  critical?: boolean;
  detail?: unknown;
  [k: string]: unknown;
};

export type SessionRow = {
  session: string;
  level: string;
  critical_mismatch: boolean;
  anomalies: DiffItem[];
  model?: { provider?: string; model_id?: string } | null;
  files: string[];
};

export type RunRow = {
  run_id: string;
  sessions: number;
  level: string;
  anomaly: boolean;
  mismatches: Array<{ session: string; item: string }>;
};

export type Injection = {
  intended: Record<string, any> | null;
  effective: Record<string, any> | null;
  diff: { level: string; items: DiffItem[] } | null;
  first_request: Record<string, any> | null;
};

export const INJECTION_TONE: Record<string, string> = { ok: "ok", warn: "warn", mismatch: "fail", unknown: "off" };
export const INJECTION_LEVEL_LABEL: Record<string, string> = {
  ok: "一致",
  warn: "提示",
  mismatch: "注入异常",
  unknown: "未知",
};

export async function getRunJson<T>(url: string): Promise<T> {
  const r = await apiFetch(url);
  const data = await r.json();
  if (!r.ok) throw new Error((data && data.detail) || `HTTP ${r.status}`);
  return data as T;
}

export function sessionFileUrl(run: string, session: string, name: string, download = false) {
  const q = new URLSearchParams({ name, ...(download ? { download: "true" } : {}) });
  return `/api/runs/${encodeURIComponent(run)}/sessions/${encodeURIComponent(session)}/file?${q}`;
}
