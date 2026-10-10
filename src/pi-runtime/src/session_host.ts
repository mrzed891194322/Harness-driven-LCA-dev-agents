import fs from "node:fs";
import path from "node:path";
import {
  createAgentSession,
  createMcpExtension,
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager,
} from "@earendil-works/pi-coding-agent";
import type { ModelProfile, SessionLaunchSpec } from "./types.js";
import {
  materializeAuthJson,
  materializeModelsJson,
  providerHasAuth,
  readPiAuthFile,
} from "./auth_materialize.js";
import {
  declaredEndpointFromFile,
  modelIsServed,
  probeServedModelIds,
} from "./live_models.js";
import {
  cancelAuthPrompt,
  replyAuthPrompt,
  runProviderLogin,
  runProviderLogout,
} from "./auth_login.js";
import { currentPeer, emitEvent, listPeers } from "./protocol.js";
import { ActivityRelay } from "./activity.js";
import { shutdownPiSession } from "./lifecycle.js";
import { PathGuard, type GuardRecord } from "./path_guard.js";
import {
  buildEffective,
  firstRequestRecord,
  knownSecrets,
  mcpConfigNames,
  redact,
  sessionSnapshotDir,
  writeJson,
} from "./injection.js";

const PROTOCOL_VERSION = 1;

type AgentSession = Awaited<ReturnType<typeof createAgentSession>>["session"];

interface LiveSession {
  spec: SessionLaunchSpec;
  piSessionId: string;
  /** Peer (connection) that created it; released when that connection closes. */
  owner: number;
  // One Pi session per assignment per run; reused across turns.
  session: AgentSession | null;
  /** Abort, emit session_shutdown (closes MCP servers), dispose. */
  dispose: () => Promise<void>;
  /** Live sink for path-guard records; set while a turn is running. */
  guardSink?: { emit: ((record: GuardRecord) => void) | null };
  /** effective.json content (real SDK state after creation, before the first model call). */
  effective: Record<string, unknown>;
  /** Live sink for the first-request injection check; set while a turn is running. */
  injectionSink?: { emit: ((record: Record<string, unknown>) => void) | null };
}

const sessions = new Map<string, LiveSession>();

const startedAt = new Date();
let transport: { transport: "stdio" | "socket"; socket: string | null } = {
  transport: "stdio",
  socket: null,
};

/** Recorded by main.ts so runtime.info can report how clients reach us. */
export function setTransportInfo(info: { transport: "stdio" | "socket"; socket: string | null }): void {
  transport = info;
}

function callerId(): number {
  return currentPeer()?.id ?? 0;
}

/** Mock is test-only infrastructure and must be requested explicitly. */
function isMockMode(): boolean {
  return process.env.PI_RUNTIME_MOCK === "1";
}

export function runtimeMode(): "real" | "mock" {
  return isMockMode() ? "mock" : "real";
}

export function liveSessionCount(): number {
  return sessions.size;
}

async function releaseSession(key: string): Promise<boolean> {
  const live = sessions.get(key);
  if (!live) return false;
  sessions.delete(key);
  await live.dispose();
  return true;
}

/** Release the sessions a peer created (its connection closed or it asked to). */
export async function releaseSessionsOwnedBy(owner: number): Promise<number> {
  const keys = [...sessions.entries()]
    .filter(([, live]) => live.owner === owner)
    .map(([key]) => key);
  await Promise.all(keys.map((key) => releaseSession(key).catch(() => false)));
  return keys.length;
}

/** Release every live session (and so every MCP child). Used on runtime exit. */
export async function disposeAllSessions(): Promise<void> {
  const keys = [...sessions.keys()];
  await Promise.all(keys.map((key) => releaseSession(key).catch(() => false)));
}

function writeMcpJson(agentDir: string, spec: SessionLaunchSpec): void {
  const servers: Record<string, unknown> = {};
  for (const [name, binding] of Object.entries(spec.mcp_bindings)) {
    if (!binding.command) {
      continue;
    }
    servers[name] = {
      command: binding.command,
      args: binding.args ?? [],
      env: binding.env ?? {},
      // Pi's MCP config takes `timeout` in SECONDS (runtime multiplies by 1000).
      // Passing ms overflowed Node's timer max and became a 1 ms init timeout.
      timeout:
        binding.timeout_ms === undefined ? undefined : Math.max(1, Math.ceil(binding.timeout_ms / 1000)),
      exposure: binding.exposure ?? "direct",
    };
  }
  if (!Object.keys(servers).length) {
    return;
  }
  fs.mkdirSync(agentDir, { recursive: true });
  fs.writeFileSync(
    path.join(agentDir, "mcp.json"),
    JSON.stringify({ mcpServers: servers }, null, 2),
    "utf8",
  );
}

/** Load MCP servers from this session's own mcp.json (not the process-wide agent dir). */
function loadSessionMcpConfig(agentDir: string) {
  const file = path.join(agentDir, "mcp.json");
  const servers: Array<{ name: string; config: any; source: string; scope: "project" }> = [];
  const errors: string[] = [];
  if (fs.existsSync(file)) {
    try {
      const parsed = JSON.parse(fs.readFileSync(file, "utf8")) as {
        mcpServers?: Record<string, unknown>;
      };
      for (const [name, config] of Object.entries(parsed.mcpServers ?? {})) {
        servers.push({ name, config, source: file, scope: "project" });
      }
    } catch (error) {
      errors.push(`${file}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  return { servers, errors, autoEnableCodemode: false };
}

function mcpLogPath(spec: SessionLaunchSpec): string {
  const root = spec.resource_bindings.project_root ?? process.cwd();
  const dir = path.join(root, ".local", "runs", spec.run_id || "adhoc", "pi");
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, `${spec.session_key}.mcp.log`);
}

function guardLogPath(spec: SessionLaunchSpec): string {
  const root = spec.resource_bindings.project_root ?? process.cwd();
  return path.join(root, ".local", "runs", spec.run_id || "adhoc", "pi", `${spec.session_key}.guard.jsonl`);
}

function systemPromptFromSpec(spec: SessionLaunchSpec): string {
  const parts = spec.system_sections.map((s) => s.content);
  if (spec.knowledge_bindings.length) {
    parts.push(
      "# 知识资料（受控读取）\n" +
        spec.knowledge_bindings
          .map(
            (k) =>
              `- ${k.id}: ${k.root_path} (hash=${k.content_hash})${k.summary ? ` — ${k.summary}` : ""}`,
          )
          .join("\n"),
    );
  }
  return parts.join("\n\n");
}

function prepareAgentDir(spec: SessionLaunchSpec): {
  authPath: string;
  modelsPath: string | null;
} {
  const agentDir = spec.session_storage.agent_dir;
  fs.mkdirSync(agentDir, { recursive: true });
  const authPath = materializeAuthJson(
    spec.resource_bindings.credentials_dir,
    agentDir,
  );
  const modelsPath = materializeModelsJson(
    spec.model_profile,
    agentDir,
    spec.resource_bindings.credentials_dir,
  );
  writeMcpJson(agentDir, spec);
  return { authPath, modelsPath };
}

async function createModelRuntimeForSpec(spec: SessionLaunchSpec): Promise<ModelRuntime> {
  const { authPath, modelsPath } = prepareAgentDir(spec);
  return ModelRuntime.create({
    authPath,
    modelsPath,
    allowModelNetwork: false,
  });
}

async function resolveModel(
  modelRuntime: ModelRuntime,
  profile: ModelProfile | undefined,
) {
  if (!profile?.provider || !profile?.model_id) {
    return undefined;
  }
  return modelRuntime.getModel(profile.provider, profile.model_id);
}

const MCP_READY_TIMEOUT_MS = 90_000;

/** Fail session creation when a bound MCP server registered no tools (connection failed). */
async function assertMcpServersReady(
  session: { getAllTools(): Array<{ name: string }> },
  spec: SessionLaunchSpec,
): Promise<void> {
  const wanted = Object.entries(spec.mcp_bindings)
    .filter(([, binding]) => binding.command && (binding.exposure ?? "direct") === "direct")
    .map(([name]) => name);
  if (!wanted.length) return;
  const deadline = Date.now() + MCP_READY_TIMEOUT_MS;
  let missing = wanted;
  while (true) {
    const names = session.getAllTools().map((t) => t.name);
    missing = wanted.filter((server) => !names.some((n) => n.startsWith(`mcp__${server}__`)));
    if (!missing.length) return;
    if (Date.now() > deadline) break;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(
    `MCP 服务未就绪（未注册任何工具）：${missing.join(", ")}；详见 ${mcpLogPath(spec)}`,
  );
}

async function createPiSession(spec: SessionLaunchSpec): Promise<LiveSession> {
  if (isMockMode()) {
    prepareAgentDir(spec);
    return {
      spec,
      owner: callerId(),
      piSessionId: `mock-${spec.session_key}`,
      session: null,
      dispose: async () => {},
      effective: {
        schema: "harness.injection.effective/1",
        captured: false,
        source: "mock",
        reason: "PI_RUNTIME_MOCK=1：没有真实 Pi SDK 会话，无法读取实际生效状态",
        session_key: spec.session_key,
      },
    };
  }

  const agentDir = spec.session_storage.agent_dir;
  const sessionFile = spec.session_storage.session_file;
  fs.mkdirSync(path.dirname(sessionFile), { recursive: true });

  const modelRuntime = await createModelRuntimeForSpec(spec);
  const model = await resolveModel(modelRuntime, spec.model_profile);
  if (!model) {
    throw new Error(
      `模型不可用：${spec.model_profile?.provider}/${spec.model_profile?.model_id}`,
    );
  }

  const cwd = spec.resource_bindings.project_root ?? process.cwd();
  const guardSink: { emit: ((record: GuardRecord) => void) | null } = { emit: null };
  const injectionSink: { emit: ((record: Record<string, unknown>) => void) | null } = { emit: null };
  const hooks = { guardMounted: false, firstRequestHook: false, firstRequestSeen: false };
  const secrets = knownSecrets(spec);
  let sessionRef: AgentSession | null = null;
  const guard = new PathGuard({
    sessionKey: spec.session_key,
    cwd,
    readGlobs: spec.permission_policy.allowed_read_globs ?? [],
    writeGlobs: spec.permission_policy.allowed_write_globs ?? [],
    deniedWriteGlobs: spec.permission_policy.denied_write_globs ?? [],
    logFile: guardLogPath(spec),
    notify: (record) => guardSink.emit?.(record),
  });
  const resourceLoader = new DefaultResourceLoader({
    cwd,
    agentDir,
    noSkills: true,
    noPromptTemplates: true,
    noThemes: true,
    noContextFiles: true,
    systemPrompt: systemPromptFromSpec(spec),
    extensionFactories: [
      (pi) => {
        pi.on("tool_call", (event) => guard.onToolCall(event.toolName, event.input as Record<string, unknown>));
        hooks.guardMounted = true;
        // Record (never modify) the first provider payload of this session object.
        pi.on("before_provider_request", (event) => {
          if (hooks.firstRequestSeen) return undefined;
          hooks.firstRequestSeen = true;
          try {
            const record = firstRequestRecord(event.payload, sessionRef?.systemPrompt ?? "", secrets);
            writeJson(path.join(sessionSnapshotDir(spec), "injection", "first_request.json"), record);
            injectionSink.emit?.({
              system_prompt_found: record.system_prompt_found,
              tool_names: record.tool_names,
              bytes: record.bytes,
            });
          } catch {
            // Diagnostics only; never break the model call.
          }
          return undefined;
        });
        hooks.firstRequestHook = true;
      },
      createMcpExtension({
        loadConfig: () => loadSessionMcpConfig(agentDir) as any,
        logPath: mcpLogPath(spec),
      }),
    ],
  });
  await resourceLoader.reload();

  const tools = spec.permission_policy.allowed_tools;
  const { session } = await createAgentSession({
    cwd,
    agentDir,
    model,
    modelRuntime,
    resourceLoader,
    // Persist to the launch spec's session_file so resume can reopen it.
    // open() starts a fresh session at that path when the file does not exist yet.
    sessionManager: SessionManager.open(sessionFile, path.dirname(sessionFile), cwd),
    tools: tools.length ? tools : undefined,
    noTools: tools.length === 0 ? "all" : undefined,
  });
  // Emits session_start: the MCP extension only connects its servers (and registers
  // mcp__<server>__<tool>) on that event; the first prompt then waits for direct tools.
  await session.bindExtensions({});
  try {
    await assertMcpServersReady(session, spec);
  } catch (error) {
    // Do not leave the servers that did start running behind a failed create.
    await shutdownPiSession(session);
    throw error;
  }
  sessionRef = session;
  let effective: Record<string, unknown>;
  try {
    effective = redact(
      buildEffective(spec, session as any, resourceLoader as any, {
        guardMounted: hooks.guardMounted,
        firstRequestHook: hooks.firstRequestHook,
        mcpConfig: mcpConfigNames(agentDir),
      }),
      secrets,
    );
  } catch (error) {
    effective = {
      schema: "harness.injection.effective/1",
      captured: false,
      source: "pi-sdk",
      reason: `读取 SDK 状态失败：${error instanceof Error ? error.message : String(error)}`,
    };
  }

  return {
    spec,
    owner: callerId(),
    piSessionId: session.sessionId,
    session,
    dispose: () => shutdownPiSession(session),
    guardSink,
    effective,
    injectionSink,
  };
}

async function testModelConnection(params: Record<string, unknown>): Promise<unknown> {
  if (isMockMode()) {
    return { ok: true, mode: "mock" };
  }
  const provider = String(params.provider ?? "").trim();
  const modelId = String(params.model_id ?? "").trim();
  const credentialsDir = String(params.credentials_dir ?? "").trim();
  const agentDir =
    String(params.agent_dir ?? "").trim() ||
    path.join(process.cwd(), "workspace", "tmp", "pi-sdk", "probe");
  fs.mkdirSync(agentDir, { recursive: true });

  const profile = {
    profile_id: "probe",
    provider,
    model_id: modelId,
    api_type: String(params.api_type ?? ""),
    base_url: String(params.base_url ?? ""),
  } satisfies ModelProfile;

  const authPath = materializeAuthJson(credentialsDir || undefined, agentDir);
  const modelsPath = materializeModelsJson(
    profile,
    agentDir,
    credentialsDir || undefined,
  );
  const auth = readPiAuthFile(authPath);
  if (provider && !providerHasAuth(auth, provider)) {
    // Compatible endpoints may use models.json apiKey (e.g. local Ollama).
    const hasCustomEndpoint = Boolean(profile.api_type || profile.base_url);
    if (!hasCustomEndpoint) {
      return { ok: false, message: `未配置 ${provider} 凭证（API Key 或 OAuth）` };
    }
  }

  const modelRuntime = await ModelRuntime.create({
    authPath,
    modelsPath,
    allowModelNetwork: false,
  });
  if (provider && modelId) {
    const model = modelRuntime.getModel(provider, modelId);
    if (!model) {
      return { ok: false, message: `模型不在 Pi catalog：${provider}/${modelId}` };
    }
  }
  if (provider && !modelRuntime.hasConfiguredAuth(provider)) {
    return { ok: false, message: `${provider} 凭证未生效` };
  }
  return { ok: true, provider, model_id: modelId };
}

async function listAvailableModels(params: Record<string, unknown>): Promise<unknown> {
  const provider = String(params.provider ?? "").trim();
  if (!provider) {
    return { ok: false, provider: "", models: [], message: "provider required" };
  }
  const credentialsDir = String(params.credentials_dir ?? "").trim();
  const agentDir =
    String(params.agent_dir ?? "").trim() ||
    path.join(process.cwd(), "workspace", "tmp", "pi-sdk", "catalog");
  fs.mkdirSync(agentDir, { recursive: true });
  const authPath = materializeAuthJson(credentialsDir || undefined, agentDir);
  const modelsPath = materializeModelsJson(undefined, agentDir, credentialsDir || undefined);
  const modelRuntime = await ModelRuntime.create({
    authPath,
    modelsPath,
    allowModelNetwork: false,
  });
  if (!modelRuntime.hasConfiguredAuth(provider)) {
    return { ok: false, provider, models: [], message: `${provider} 凭证未生效` };
  }
  const declared = declaredEndpointFromFile(modelsPath, provider);
  let served: ReadonlySet<string> | null = null;
  if (declared) {
    const probe = await probeServedModelIds(declared.baseUrl, declared.apiKey);
    if (!probe.ok) {
      return { ok: false, provider, models: [], message: probe.message };
    }
    served = probe.ids;
  }
  try {
    const catalog = await modelRuntime.getAvailable(provider);
    const models = catalog
      .filter((model) => model.provider === provider && model.id)
      .flatMap((model) => {
        const loaded = modelRuntime.getModel(provider, model.id);
        if (!loaded?.id) return [];
        if (served && !modelIsServed(served, loaded.id)) return [];
        return [{ id: loaded.id, name: loaded.name || loaded.id }];
      })
      .sort((a, b) => a.id.localeCompare(b.id));
    const missing =
      served !== null && models.length === 0
        ? "端点在线，但没有已配置且实际存在的模型。"
        : "";
    return {
      ok: true,
      provider,
      models,
      message: missing || modelRuntime.getError() || "",
    };
  } catch (error) {
    return {
      ok: false,
      provider,
      models: [],
      message: error instanceof Error ? error.message : String(error),
    };
  }
}

/**
 * Register a freshly created session -- unless its connection closed while it was
 * being created (then nobody would ever release it): dispose it right away.
 */
async function adoptSession(key: string, live: LiveSession): Promise<void> {
  const ownerGone = live.owner !== 0 && !listPeers().some((peer) => peer.id === live.owner);
  if (ownerGone) {
    await live.dispose();
    throw new Error(`connection #${live.owner} closed during session creation; released ${key}`);
  }
  sessions.set(key, live);
}

export function runtimeInfo(): Record<string, unknown> {
  const live = [...sessions.entries()];
  return {
    pid: process.pid,
    mode: runtimeMode(),
    transport: transport.transport,
    socket: transport.socket,
    started_at: startedAt.toISOString(),
    uptime_s: Math.round((Date.now() - startedAt.getTime()) / 1000),
    connection_id: callerId(),
    connections: listPeers().map((peer) => ({
      id: peer.id,
      label: peer.label,
      connected_at: peer.connectedAt,
      sessions: live.filter(([, s]) => s.owner === peer.id).length,
    })),
    sessions: live.map(([key, s]) => ({
      session_key: key,
      owner: s.owner,
      run_id: s.spec.run_id,
      stage_id: s.spec.stage_id,
      role: s.spec.role,
    })),
  };
}

export async function handleRuntimeMethod(
  method: string,
  params: Record<string, unknown>,
): Promise<unknown> {
  if (method === "protocol.version") {
    return { version: PROTOCOL_VERSION };
  }
  if (method === "session.create") {
    const spec = params.launch_spec as SessionLaunchSpec;
    if (!spec || spec.schema_version !== 1) {
      throw new Error("invalid launch_spec");
    }
    await releaseSession(spec.session_key);
    const live = await createPiSession(spec);
    await adoptSession(spec.session_key, live);
    return {
      session_key: spec.session_key,
      pi_session_id: live.piSessionId,
      storage: spec.session_storage,
      effective: live.effective,
    };
  }
  if (method === "session.resume") {
    const spec = params.launch_spec as SessionLaunchSpec;
    const key = String(params.session_key ?? spec?.session_key ?? "");
    const sessionFile = spec.session_storage.session_file;
    if (!fs.existsSync(sessionFile) && !isMockMode()) {
      throw new Error(`session file missing: ${sessionFile}`);
    }
    await releaseSession(key);
    const live = await createPiSession(spec);
    await adoptSession(key, live);
    return {
      session_key: key,
      pi_session_id: live.piSessionId,
      storage: spec.session_storage,
      effective: live.effective,
    };
  }
  if (method === "session.run_turn") {
    const key = String(params.session_key ?? "");
    const prompt = String(params.prompt ?? "");
    const live = sessions.get(key);
    if (!live) {
      throw new Error(`unknown session ${key}`);
    }
    // Turn output goes to the connection that asked for the turn.
    const peer = currentPeer();
    const relay = new ActivityRelay(key, (event) => emitEvent("turn.event", { ...event }, peer));
    if (isMockMode()) {
      emitEvent("turn.progress", { session_key: key, line: "[mock] turn complete\n" }, peer);
      relay.handle({ type: "message_update", assistantMessageEvent: { type: "text_delta", delta: "[mock] turn complete" } });
      relay.finish("ok");
      return { status: "ok", text: `[mock] received ${prompt.length} chars` };
    }
    const session = live.session;
    if (!session) {
      throw new Error(`session ${key} has no live Pi session`);
    }
    let text = "";
    if (live.guardSink) {
      live.guardSink.emit = (record) => {
        if (record.action === "bash_command" && !record.out_of_scope) return;
        emitEvent(
          "turn.event",
          {
            session_key: key,
            kind: "permission",
            ts: record.ts,
            tool: record.tool,
            summary:
              record.action === "denied"
                ? `拒绝 ${record.tool} ${record.requested_path} -> ${record.resolved_path}`
                : `bash 越界路径：${(record.out_of_scope ?? []).map((f) => f.resolved).join(", ")}`,
            is_error: record.action === "denied",
            args: { ...record },
          },
          peer,
        );
      };
    }
    if (live.injectionSink) {
      live.injectionSink.emit = (record) =>
        emitEvent(
          "turn.event",
          {
            session_key: key,
            kind: "injection_payload",
            ts: new Date().toISOString(),
            summary: record.system_prompt_found
              ? "首次模型请求包含注入的 system prompt"
              : "首次模型请求中未找到注入的 system prompt",
            is_error: !record.system_prompt_found,
            args: record,
          },
          peer,
        );
    }
    const unsub = session.subscribe((ev) => {
      if (ev.type === "message_update" && ev.assistantMessageEvent?.type === "text_delta") {
        const delta = ev.assistantMessageEvent.delta ?? "";
        text += delta;
        emitEvent("turn.progress", { session_key: key, line: delta }, peer);
      }
      try {
        relay.handle(ev as { type: string });
      } catch {
        // Activity is best-effort UI telemetry; never break the turn over it.
      }
    });
    try {
      await session.prompt(prompt);
      relay.finish("ok");
    } catch (error) {
      relay.finish("error", error instanceof Error ? error.message : String(error));
      throw error;
    } finally {
      unsub();
      if (live.guardSink) live.guardSink.emit = null;
      if (live.injectionSink) live.injectionSink.emit = null;
    }
    return { status: "ok", text };
  }
  if (method === "session.inspect") {
    // Re-read effective state of a live session (doctor / debugging), no model call.
    const key = String(params.session_key ?? "");
    const live = sessions.get(key);
    if (!live) throw new Error(`unknown session ${key}`);
    return { session_key: key, effective: live.effective };
  }
  if (method === "session.release") {
    const key = String(params.session_key ?? "");
    const released = await releaseSession(key);
    return { released };
  }
  if (method === "session.release_all") {
    // Only the caller's own sessions: other clients share this runtime.
    if (params.all === true) {
      const count = sessions.size;
      await disposeAllSessions();
      return { released: count };
    }
    return { released: await releaseSessionsOwnedBy(callerId()) };
  }
  if (method === "client.hello") {
    const peer = currentPeer();
    const label = String(params.label ?? "").trim().slice(0, 200);
    if (peer && label) peer.label = label;
    return { connection_id: peer?.id ?? 0, pid: process.pid, mode: runtimeMode() };
  }
  if (method === "session.cancel") {
    const key = String(params.session_key ?? "");
    const session = sessions.get(key)?.session;
    if (!session) {
      return { cancelled: false };
    }
    await session.abort();
    return { cancelled: true };
  }
  if (method === "runtime.info") {
    return runtimeInfo();
  }
  if (method === "models.test_connection") {
    return testModelConnection(params);
  }
  if (method === "models.list_available") {
    return listAvailableModels(params);
  }
  if (method === "auth.login") {
    return runProviderLogin(params);
  }
  if (method === "auth.logout") {
    return runProviderLogout(params);
  }
  if (method === "auth.prompt_reply") {
    const promptId = String(params.prompt_id ?? "").trim();
    const value = String(params.value ?? "");
    if (!promptId) {
      throw new Error("prompt_id required");
    }
    if (!replyAuthPrompt(promptId, value)) {
      throw new Error(`unknown prompt_id: ${promptId}`);
    }
    return { ok: true };
  }
  if (method === "auth.prompt_cancel") {
    const promptId = String(params.prompt_id ?? "").trim();
    if (!promptId) {
      throw new Error("prompt_id required");
    }
    cancelAuthPrompt(promptId);
    return { ok: true };
  }
  throw new Error(`unknown method: ${method}`);
}
