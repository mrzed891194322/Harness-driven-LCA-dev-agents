import fs from "node:fs";
import path from "node:path";
import type { ModelProfile } from "./types.js";

/**
 * Pi auth.json credential shapes (see @earendil-works/pi-ai Auth types):
 * - api_key: { type: "api_key", key }
 * - oauth:  { type: "oauth", access, refresh, expires, ... }
 */
export type PiAuthEntry = Record<string, unknown> & {
  type?: string;
  key?: string;
  apiKey?: string;
  access?: string;
  refresh?: string;
  expires?: number;
};

/** Pi auth.json: top-level map of providerId → credential. */
export type PiAuthFile = Record<string, PiAuthEntry>;

export type PiModelsFile = {
  providers?: Record<string, Record<string, unknown>>;
};

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
    const type = String(entry.type || "").trim();
    if (type === "oauth" || entry.access || entry.refresh) {
      const access = String(entry.access ?? "").trim();
      const refresh = String(entry.refresh ?? "").trim();
      if (!access && !refresh) {
        continue;
      }
      out[provider] = { ...entry, type: "oauth" };
      continue;
    }
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

export function readPiModelsFile(modelsPath: string): PiModelsFile {
  if (!fs.existsSync(modelsPath)) {
    return {};
  }
  try {
    const raw = JSON.parse(fs.readFileSync(modelsPath, "utf8")) as unknown;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      return {};
    }
    return raw as PiModelsFile;
  } catch {
    return {};
  }
}

/**
 * Build agent models.json from Pi's documented shape:
 * - Compatible endpoint: providers.<id> = { baseUrl, api, apiKey?, models[] }
 * - Built-in override: providers.<id> = { baseUrl } (no models → keep catalog)
 * See pi-coding-agent docs/models.md § Configure a compatible endpoint.
 */
export function materializeModelsJson(
  profile: ModelProfile | undefined,
  agentDir: string,
  credentialsDir?: string,
): string | null {
  const providers: Record<string, Record<string, unknown>> = {};

  if (credentialsDir) {
    const stored = readPiModelsFile(path.join(credentialsDir, "pi-models.json"));
    for (const [id, cfg] of Object.entries(stored.providers ?? {})) {
      if (cfg && typeof cfg === "object") {
        providers[id] = { ...cfg };
      }
    }
  }

  if (profile) {
    const apiType = (profile.api_type || "").trim();
    const baseUrl = (profile.base_url || "").trim();
    const provider = (profile.provider || "custom").trim() || "custom";
    const modelId = (profile.model_id || "").trim();
    if (apiType || baseUrl) {
      const existing = providers[provider] ? { ...providers[provider] } : {};
      if (baseUrl) {
        existing.baseUrl = baseUrl;
      }
      if (apiType) {
        existing.api = apiType;
      }
      // Custom/compatible endpoint: register the profile model.
      // Built-in baseUrl-only override: omit models so catalog stays.
      if (apiType && modelId) {
        existing.models = [
          {
            id: modelId,
            name: profile.display_name || modelId,
          },
        ];
        if (!existing.apiKey) {
          // Pi docs: dummy key makes local servers (Ollama) available.
          existing.apiKey = "local";
        }
      }
      providers[provider] = existing;
    }
  }

  if (!Object.keys(providers).length) {
    const existing = path.join(agentDir, "models.json");
    if (fs.existsSync(existing)) {
      return existing;
    }
    return null;
  }

  fs.mkdirSync(agentDir, { recursive: true });
  const dest = path.join(agentDir, "models.json");
  fs.writeFileSync(dest, `${JSON.stringify({ providers }, null, 2)}\n`, "utf8");
  return dest;
}

export function providerHasKey(auth: PiAuthFile, provider: string): boolean {
  return providerHasAuth(auth, provider);
}

/** True when api_key or oauth credential is present (Pi auth.json). */
export function providerHasAuth(auth: PiAuthFile, provider: string): boolean {
  const entry = auth[provider];
  if (!entry) {
    return false;
  }
  if (entry.type === "oauth" || entry.access || entry.refresh) {
    return Boolean(String(entry.access ?? "").trim() || String(entry.refresh ?? "").trim());
  }
  return Boolean(String(entry.key ?? entry.apiKey ?? "").trim());
}
