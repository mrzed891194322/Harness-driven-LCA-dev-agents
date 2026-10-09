import { readPiModelsFile, type PiModelsFile } from "./auth_materialize.js";

export type DeclaredEndpoint = {
  baseUrl: string;
  apiKey: string;
  modelIds: string[];
};

/** User-declared compatible endpoint. BaseURL-only catalog overrides return null. */
export function declaredEndpoint(
  models: PiModelsFile,
  provider: string,
): DeclaredEndpoint | null {
  const entry = models.providers?.[provider];
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const rawModels = entry.models;
  if (!Array.isArray(rawModels) || rawModels.length === 0) {
    return null;
  }
  const modelIds = rawModels
    .map((item) => {
      if (!item || typeof item !== "object") return "";
      return String((item as { id?: unknown }).id ?? "").trim();
    })
    .filter(Boolean);
  if (!modelIds.length) {
    return null;
  }
  return {
    baseUrl: String(entry.baseUrl ?? "").trim(),
    apiKey: String(entry.apiKey ?? "").trim(),
    modelIds,
  };
}

export function declaredEndpointFromFile(
  modelsPath: string | null | undefined,
  provider: string,
): DeclaredEndpoint | null {
  if (!modelsPath) return null;
  return declaredEndpoint(readPiModelsFile(modelsPath), provider);
}

export function probeUrls(baseUrl: string): string[] {
  const base = baseUrl.replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(base)) return [];
  const urls = [`${base}/models`];
  if (base.endsWith("/v1")) {
    urls.push(`${base.slice(0, -3)}/api/tags`);
  }
  return urls;
}

export function collectServedModelIds(payload: unknown): Set<string> {
  const ids = new Set<string>();
  if (!payload || typeof payload !== "object") return ids;
  const record = payload as { data?: unknown; models?: unknown };
  const rows = [
    ...(Array.isArray(record.data) ? record.data : []),
    ...(Array.isArray(record.models) ? record.models : []),
  ];
  for (const item of rows) {
    if (typeof item === "string") {
      const name = item.trim();
      if (name) ids.add(name);
      continue;
    }
    if (!item || typeof item !== "object") continue;
    const row = item as { id?: unknown; name?: unknown; model?: unknown };
    for (const value of [row.id, row.name, row.model]) {
      if (typeof value === "string" && value.trim()) ids.add(value.trim());
    }
  }
  return ids;
}

export function modelIsServed(served: ReadonlySet<string>, modelId: string): boolean {
  const id = modelId.trim();
  if (!id || served.size === 0) return false;
  if (served.has(id)) return true;
  for (const name of served) {
    if (name === `${id}:latest` || id === `${name}:latest`) return true;
  }
  return false;
}

export async function probeServedModelIds(
  baseUrl: string,
  apiKey: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ ok: true; ids: Set<string> } | { ok: false; message: string }> {
  const urls = probeUrls(baseUrl);
  if (!urls.length) {
    return { ok: false, message: "无法连接端点，不能确认模型已安装。" };
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
  const ids = new Set<string>();
  let connected = false;
  let lastStatus = 0;
  for (const url of urls) {
    try {
      const response = await fetchImpl(url, {
        headers,
        signal: AbortSignal.timeout(4000),
      });
      if (!response.ok) {
        connected = true;
        lastStatus = response.status;
        continue;
      }
      connected = true;
      const payload: unknown = await response.json();
      for (const id of collectServedModelIds(payload)) ids.add(id);
    } catch {
      continue;
    }
  }
  if (ids.size > 0 || (connected && lastStatus === 0)) {
    return { ok: true, ids };
  }
  if (connected) {
    return {
      ok: false,
      message: `端点返回 HTTP ${lastStatus}，不能确认模型已安装。`,
    };
  }
  return { ok: false, message: "无法连接端点，不能确认模型已安装。" };
}
