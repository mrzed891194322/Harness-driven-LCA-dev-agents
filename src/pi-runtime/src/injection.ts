/**
 * Injection manifest, runtime side: what the Pi SDK session ACTUALLY has after creation
 * and before the first model call (effective.json), plus the first provider request
 * payload when the SDK's before_provider_request hook fires (first_request.json).
 * The host writes intended.json and diffs the two (backend/core/agents/injection.py).
 * Everything leaving here is redacted; nothing is inferred from the launch spec.
 */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import type { SessionLaunchSpec } from "./types.js";

export const REDACTED = "[REDACTED]";
const SENSITIVE_KEY = /(api[_-]?key|token|secret|password|passwd|authorization|cookie|signing|private[_-]?key|credential)/i;
const SECRET_PATTERNS: RegExp[] = [
  /\bsk-[A-Za-z0-9_\-]{12,}/g,
  /\bBearer\s+[A-Za-z0-9._\-~+/=]{12,}/g,
  /\bgh[pousr]_[A-Za-z0-9]{20,}/g,
  /\bxox[abpr]-[A-Za-z0-9-]{10,}/g,
  /\bAIza[0-9A-Za-z_\-]{30,}/g,
];

export function sha256(text: string): string {
  return crypto.createHash("sha256").update(text, "utf8").digest("hex");
}

/** Secret VALUES known to this process: sensitive-named env vars and MCP binding env. */
export function knownSecrets(spec?: SessionLaunchSpec): string[] {
  const out = new Set<string>();
  const add = (k: string, v: unknown) => {
    if (typeof v === "string" && v.length >= 8 && SENSITIVE_KEY.test(k)) out.add(v);
  };
  for (const [k, v] of Object.entries(process.env)) add(k, v);
  for (const binding of Object.values(spec?.mcp_bindings ?? {})) {
    for (const [k, v] of Object.entries(binding.env ?? {})) add(k, v);
  }
  return [...out].sort((a, b) => b.length - a.length);
}

export function redactString(text: string, secrets: string[]): string {
  let out = text;
  for (const s of secrets) if (out.includes(s)) out = out.split(s).join(REDACTED);
  for (const re of SECRET_PATTERNS) out = out.replace(re, REDACTED);
  return out;
}

export function redact<T>(value: T, secrets: string[]): T {
  const walk = (v: unknown, key = ""): unknown => {
    if (typeof v === "string") return key && SENSITIVE_KEY.test(key) && v ? REDACTED : redactString(v, secrets);
    if (Array.isArray(v)) return v.map((x) => walk(x));
    if (v && typeof v === "object") {
      const o: Record<string, unknown> = {};
      for (const [k, x] of Object.entries(v as Record<string, unknown>)) {
        o[k] = typeof x === "string" && SENSITIVE_KEY.test(k) && x ? REDACTED : walk(x, k);
      }
      return o;
    }
    return v;
  };
  return walk(value) as T;
}

/** .local/runs/<run>/sessions/<stage>.<role>.<attempt>/ — kept per run, outside workspace/. */
export function sessionSnapshotDir(spec: SessionLaunchSpec): string {
  const root = spec.resource_bindings.project_root ?? process.cwd();
  const safe = (s: string) => String(s || "x").replace(/[^A-Za-z0-9._-]/g, "_");
  return path.join(
    root,
    ".local",
    "runs",
    safe(spec.run_id || "adhoc"),
    "sessions",
    `${safe(spec.stage_id)}.${safe(spec.role)}.${Number(spec.attempt) || 0}`,
  );
}

export function writeJson(file: string, data: unknown): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2) + "\n", "utf8");
  fs.renameSync(tmp, file);
}

interface ToolInfoLike {
  name: string;
  description?: string;
  parameters?: unknown;
  exposure?: string;
  sourceInfo?: { path?: string; source?: string };
}

interface SessionLike {
  systemPrompt: string;
  model?: { provider?: string; id?: string; api?: string; baseUrl?: string; reasoning?: boolean; contextWindow?: number; maxTokens?: number };
  thinkingLevel?: string;
  sessionId: string;
  sessionFile?: string;
  getActiveToolNames(): string[];
  getAllTools(): ToolInfoLike[];
  extensionRunner?: { hasHandlers(e: string): boolean; getExtensionPaths?(): string[] };
}

interface LoaderLike {
  getSkills(): { skills: Array<{ name?: string; filePath?: string; path?: string }> };
  getExtensions(): { extensions: Array<{ path: string; resolvedPath?: string }>; errors: Array<{ path: string; error: string }> };
}

export interface EffectiveExtras {
  guardMounted: boolean;
  firstRequestHook: boolean;
  mcpConfig: unknown;
}

/** Read the real SDK state (never the launch spec) into effective.json. */
export function buildEffective(
  spec: SessionLaunchSpec,
  session: SessionLike,
  loader: LoaderLike,
  extras: EffectiveExtras,
): Record<string, unknown> {
  const active = new Set(session.getActiveToolNames());
  const all = session.getAllTools();
  const tools = all
    .map((t) => ({
      name: t.name,
      active: active.has(t.name),
      exposure: t.exposure ?? null,
      source: t.sourceInfo?.source ?? t.sourceInfo?.path ?? null,
      description: t.description ?? "",
      parameters: t.parameters ?? null,
      schema_hash: sha256(JSON.stringify(t.parameters ?? null)),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
  const mcpServers: Record<string, { tools: string[]; exposures: string[] }> = {};
  for (const t of tools) {
    const m = /^mcp__(.+?)__/.exec(t.name);
    if (!m) continue;
    const s = (mcpServers[m[1]] ??= { tools: [], exposures: [] });
    s.tools.push(t.name);
    if (t.exposure && !s.exposures.includes(t.exposure)) s.exposures.push(t.exposure);
  }
  let skills: string[] = [];
  let extensions: string[] = [];
  let extensionErrors: unknown[] = [];
  try {
    skills = loader.getSkills().skills.map((s) => s.name ?? s.filePath ?? s.path ?? "?");
  } catch {
    skills = [];
  }
  try {
    const ext = loader.getExtensions();
    extensions = ext.extensions.map((e) => e.path);
    extensionErrors = ext.errors;
  } catch {
    extensions = [];
  }
  const systemPrompt = session.systemPrompt ?? "";
  return {
    schema: "harness.injection.effective/1",
    captured: true,
    source: "pi-sdk",
    captured_at: new Date().toISOString(),
    session_key: spec.session_key,
    pi_session_id: session.sessionId,
    pi_session_file: session.sessionFile ?? null,
    system_prompt: systemPrompt,
    system_prompt_hash: sha256(systemPrompt),
    model: {
      provider: session.model?.provider ?? null,
      model_id: session.model?.id ?? null,
      api: session.model?.api ?? null,
      base_url: session.model?.baseUrl ?? null,
      reasoning: session.model?.reasoning ?? null,
      context_window: session.model?.contextWindow ?? null,
      max_tokens: session.model?.maxTokens ?? null,
      thinking_level: session.thinkingLevel ?? null,
    },
    tools,
    active_tool_names: [...active].sort(),
    mcp_servers: mcpServers,
    mcp_config: extras.mcpConfig,
    skills,
    extensions,
    extension_errors: extensionErrors,
    guard_hook_mounted: extras.guardMounted && Boolean(session.extensionRunner?.hasHandlers("tool_call")),
    first_request_hook: extras.firstRequestHook,
  };
}

/** mcp.json as the SDK reads it, env reduced to variable NAMES. */
export function mcpConfigNames(agentDir: string): unknown {
  const file = path.join(agentDir, "mcp.json");
  if (!fs.existsSync(file)) return { servers: {} };
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8")) as { mcpServers?: Record<string, any> };
    const servers: Record<string, unknown> = {};
    for (const [name, cfg] of Object.entries(parsed.mcpServers ?? {})) {
      servers[name] = {
        command: cfg.command ?? null,
        args: cfg.args ?? [],
        env_names: Object.keys(cfg.env ?? {}).sort(),
        timeout_s: cfg.timeout ?? null,
        exposure: cfg.exposure ?? null,
      };
    }
    return { servers };
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
}

/** Summary of the first provider payload: does it carry the system prompt / tools? */
export function firstRequestRecord(
  payload: unknown,
  systemPrompt: string,
  secrets: string[],
): Record<string, unknown> {
  const text = JSON.stringify(payload ?? null);
  const needle = JSON.stringify(systemPrompt).slice(1, -1);
  const toolNames = new Set<string>();
  const visit = (v: unknown) => {
    if (Array.isArray(v)) v.forEach(visit);
    else if (v && typeof v === "object") {
      const o = v as Record<string, any>;
      if (Array.isArray(o.tools)) {
        for (const t of o.tools) {
          const n = t?.name ?? t?.function?.name;
          if (typeof n === "string") toolNames.add(n);
        }
      }
      for (const x of Object.values(o)) if (x && typeof x === "object") visit(x);
    }
  };
  visit(payload);
  return {
    schema: "harness.injection.first_request/1",
    captured: true,
    captured_at: new Date().toISOString(),
    bytes: Buffer.byteLength(text, "utf8"),
    system_prompt_found: systemPrompt.length > 0 && text.includes(needle),
    tool_names: [...toolNames].sort(),
    payload: redact(payload, secrets),
  };
}
