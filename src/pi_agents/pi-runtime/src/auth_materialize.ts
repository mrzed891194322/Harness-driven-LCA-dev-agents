import fs from "node:fs";
import path from "node:path";
import type { ModelProfile } from "./types.js";

/** Pi auth.json: top-level map of providerId → credential. */
export type PiAuthFile = Record<string, { type?: string; key?: string; apiKey?: string }>;

export function readPiAuthFile(authPath: string): PiAuthFile {
  if (!fs.existsSync(authPath)) {
    return {};
  }
  try {
    const raw = JSON.parse(fs.readFileSync(authPath, "utf8")) as unknown;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      return {};
    }
    const obj = raw as Record<string, unknown>;
    // Legacy wrapper: { providers: { anthropic: { apiKey } } }
    if (obj.providers && typeof obj.providers === "object" && !Array.isArray(obj.providers)) {
      return normalizeAuthMap(obj.providers as Record<string, unknown>);
    }
    return normalizeAuthMap(obj);
  } catch {
    return {};
  }
}

function normalizeAuthMap(input: Record<string, unknown>): PiAuthFile {
  const out: PiAuthFile = {};
  for (const [provider, value] of Object.entries(input)) {
    if (!provider || provider === "providers") {
      continue;
    }
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      continue;
    }
    const entry = value as Record<string, unknown>;
    const key = String(entry.key ?? entry.apiKey ?? "").trim();
    if (!key) {
      continue;
    }
    out[provider] = {
      type: String(entry.type || "api_key"),
      key,
    };
  }
  return out;
}

export function materializeAuthJson(
  credentialsDir: string | undefined,
  agentDir: string,
): string {
  const dest = path.join(agentDir, "auth.json");
  fs.mkdirSync(agentDir, { recursive: true });
  if (!credentialsDir) {
    if (!fs.existsSync(dest)) {
      fs.writeFileSync(dest, "{}\n", "utf8");
    }
    return dest;
  }
  const source = path.join(credentialsDir, "pi-auth.json");
  const auth = readPiAuthFile(source);
  fs.writeFileSync(dest, `${JSON.stringify(auth, null, 2)}\n`, "utf8");
  return dest;
}

export function materializeModelsJson(
  profile: ModelProfile | undefined,
  agentDir: string,
): string | null {
  if (!profile) {
    return null;
  }
  const apiType = (profile.api_type || "").trim();
  const baseUrl = (profile.base_url || "").trim();
  if (!apiType && !baseUrl) {
    // Built-in catalog — no custom models.json needed.
    const existing = path.join(agentDir, "models.json");
    if (fs.existsSync(existing)) {
      return existing;
    }
    return null;
  }
  const provider = (profile.provider || "custom").trim() || "custom";
  const modelId = (profile.model_id || "").trim();
  const providerConfig: Record<string, unknown> = {};
  if (baseUrl) {
    providerConfig.baseUrl = baseUrl;
  }
  if (apiType) {
    providerConfig.api = apiType;
  }
  if (modelId) {
    providerConfig.models = [
      {
        id: modelId,
        name: profile.display_name || modelId,
      },
    ];
  }
  const payload = { providers: { [provider]: providerConfig } };
  fs.mkdirSync(agentDir, { recursive: true });
  const dest = path.join(agentDir, "models.json");
  fs.writeFileSync(dest, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return dest;
}

export function providerHasKey(auth: PiAuthFile, provider: string): boolean {
  const entry = auth[provider];
  return Boolean(entry?.key?.trim());
}
