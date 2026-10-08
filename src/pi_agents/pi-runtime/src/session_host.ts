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
  cancelAuthPrompt,
  replyAuthPrompt,
  runProviderLogin,
  runProviderLogout,
} from "./auth_login.js";
import { emitEvent } from "./protocol.js";

const PROTOCOL_VERSION = 1;

interface LiveSession {
  spec: SessionLaunchSpec;
  piSessionId: string;
  dispose: () => void;
}

const sessions = new Map<string, LiveSession>();

function isMockMode(): boolean {
  return process.env.PI_RUNTIME_MOCK === "1";
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
      timeout: binding.timeout_ms,
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

async function createPiSession(spec: SessionLaunchSpec): Promise<LiveSession> {
  if (isMockMode()) {
    prepareAgentDir(spec);
    return {
      spec,
      piSessionId: `mock-${spec.session_key}`,
      dispose: () => {},
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
  const resourceLoader = new DefaultResourceLoader({
    cwd,
    agentDir,
    noSkills: true,
    noPromptTemplates: true,
    noThemes: true,
    noContextFiles: true,
    systemPrompt: systemPromptFromSpec(spec),
    extensionFactories: [createMcpExtension()],
  });
  await resourceLoader.reload();

  const tools = spec.permission_policy.allowed_tools;
  const { session } = await createAgentSession({
    cwd,
    agentDir,
    model,
    modelRuntime,
    resourceLoader,
    sessionManager: SessionManager.create(cwd),
    tools: tools.length ? tools : undefined,
    noTools: tools.length === 0 ? "all" : undefined,
  });

  return {
    spec,
    piSessionId: session.sessionId,
    dispose: () => session.dispose(),
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
    const live = await createPiSession(spec);
    sessions.set(spec.session_key, live);
    return {
      session_key: spec.session_key,
      pi_session_id: live.piSessionId,
      storage: spec.session_storage,
    };
  }
  if (method === "session.resume") {
    const spec = params.launch_spec as SessionLaunchSpec;
    const key = String(params.session_key ?? spec?.session_key ?? "");
    const sessionFile = spec.session_storage.session_file;
    if (!fs.existsSync(sessionFile) && !isMockMode()) {
      throw new Error(`session file missing: ${sessionFile}`);
    }
    const live = await createPiSession(spec);
    sessions.set(key, live);
    return {
      session_key: key,
      pi_session_id: live.piSessionId,
      storage: spec.session_storage,
    };
  }
  if (method === "session.run_turn") {
    const key = String(params.session_key ?? "");
    const prompt = String(params.prompt ?? "");
    const live = sessions.get(key);
    if (!live) {
      throw new Error(`unknown session ${key}`);
    }
    if (isMockMode()) {
      emitEvent("turn.progress", { session_key: key, line: "[mock] turn complete\n" });
      return { status: "ok", text: `[mock] received ${prompt.length} chars` };
    }
    const spec = live.spec;
    const cwd = spec.resource_bindings.project_root ?? process.cwd();
    const modelRuntime = await createModelRuntimeForSpec(spec);
    const model = await resolveModel(modelRuntime, spec.model_profile);
    if (!model) {
      throw new Error(
        `模型不可用：${spec.model_profile?.provider}/${spec.model_profile?.model_id}`,
      );
    }
    const resourceLoader = new DefaultResourceLoader({
      cwd,
      agentDir: spec.session_storage.agent_dir,
      noSkills: true,
      noPromptTemplates: true,
      noThemes: true,
      noContextFiles: true,
      systemPrompt: systemPromptFromSpec(spec),
      extensionFactories: [createMcpExtension()],
    });
    await resourceLoader.reload();
    const { session } = await createAgentSession({
      cwd,
      agentDir: spec.session_storage.agent_dir,
      model,
      modelRuntime,
      resourceLoader,
      sessionManager: SessionManager.create(cwd),
      tools: spec.permission_policy.allowed_tools,
    });
    let text = "";
    const unsub = session.subscribe((ev) => {
      if (ev.type === "message_update" && ev.assistantMessageEvent?.type === "text_delta") {
        const delta = ev.assistantMessageEvent.delta ?? "";
        text += delta;
        emitEvent("turn.progress", { session_key: key, line: delta });
      }
    });
    try {
      await session.prompt(prompt);
    } finally {
      unsub();
      session.dispose();
    }
    return { status: "ok", text };
  }
  if (method === "session.release") {
    const key = String(params.session_key ?? "");
    const live = sessions.get(key);
    if (live) {
      live.dispose();
      sessions.delete(key);
    }
    return { released: true };
  }
  if (method === "session.cancel") {
    return { cancelled: true };
  }
  if (method === "models.test_connection") {
    return testModelConnection(params);
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
