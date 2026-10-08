import fs from "node:fs";
import path from "node:path";
import {
  createAgentSession,
  createMcpExtension,
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager,
} from "@earendil-works/pi-coding-agent";
import type { SessionLaunchSpec } from "./types.js";
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

async function createPiSession(spec: SessionLaunchSpec): Promise<LiveSession> {
  if (isMockMode()) {
    return {
      spec,
      piSessionId: `mock-${spec.session_key}`,
      dispose: () => {},
    };
  }

  const agentDir = spec.session_storage.agent_dir;
  const sessionFile = spec.session_storage.session_file;
  fs.mkdirSync(agentDir, { recursive: true });
  fs.mkdirSync(path.dirname(sessionFile), { recursive: true });
  writeMcpJson(agentDir, spec);

  const cwd = spec.resource_bindings.project_root ?? process.cwd();
  const modelRuntime = await ModelRuntime.create({
    authPath: path.join(agentDir, "auth.json"),
    modelsPath: path.join(agentDir, "models.json"),
  });

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
    const modelRuntime = await ModelRuntime.create({
      authPath: path.join(spec.session_storage.agent_dir, "auth.json"),
      modelsPath: path.join(spec.session_storage.agent_dir, "models.json"),
    });
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
    if (isMockMode()) {
      return { ok: true, mode: "mock" };
    }
    return { ok: false, message: "configure credentials in agent_dir before live test" };
  }
  throw new Error(`unknown method: ${method}`);
}
