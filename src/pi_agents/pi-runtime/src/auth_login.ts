/**
 * OpenAI / Anthropic OAuth via Pi's documented programmatic path.
 *
 * Pi interactive mode uses LoginDialogComponent (TUI-only) as the AuthInteraction
 * front-end, then calls the same API we use here:
 *
 *   modelRuntime.login(providerId, "oauth", { signal, prompt, notify }, {
 *     getDeviceId: () => settingsManager.getOrCreateDeviceId(),
 *   })
 *
 * See:
 * - @earendil-works/pi-ai README § Programmatic OAuth
 * - openai-chatgpt.js (requires getDeviceId UUID + localhost:1455 callback / paste URL)
 * - interactive-mode.js loginProvider()
 *
 * We intentionally do NOT reimplement PKCE / token exchange — only bridge
 * AuthInteraction over NDJSON so the Web Settings UI can drive Pi's built-in flow.
 */
import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { ModelRuntime, SettingsManager } from "@earendil-works/pi-coding-agent";
import { emitEvent } from "./protocol.js";
import { materializeModelsJson, readPiAuthFile } from "./auth_materialize.js";

/** AuthInteraction surface from Pi (pi-ai auth/types) — same contract LoginDialog satisfies. */
type AuthPrompt = {
  signal?: AbortSignal;
  type: "text" | "secret" | "select" | "manual_code";
  message: string;
  placeholder?: string;
  options?: readonly { id: string; label: string; description?: string }[];
};

type AuthEvent =
  | { type: "info"; message: string; links?: readonly { url: string; label?: string }[] }
  | { type: "auth_url"; url: string; instructions?: string }
  | {
      type: "device_code";
      userCode: string;
      verificationUri: string;
      intervalSeconds?: number;
      expiresInSeconds?: number;
    }
  | { type: "progress"; message: string };

type AuthInteraction = {
  signal?: AbortSignal;
  prompt(prompt: AuthPrompt): Promise<string>;
  notify(event: AuthEvent): void;
};

type PendingPrompt = {
  resolve: (value: string) => void;
  reject: (err: Error) => void;
};

const pendingPrompts = new Map<string, PendingPrompt>();

/** Providers whose Pi factory registers OAuthAuth (pi-ai README § OAuth Providers). */
const OAUTH_PROVIDERS = new Set([
  "openai",
  "anthropic",
  "github-copilot",
  "openrouter",
  "openai-codex",
]);

function ensureAuthFile(credentialsDir: string): string {
  fs.mkdirSync(credentialsDir, { recursive: true });
  const authPath = path.join(credentialsDir, "pi-auth.json");
  if (!fs.existsSync(authPath)) {
    fs.writeFileSync(authPath, "{}\n", "utf8");
  }
  return authPath;
}

/**
 * Stable installation device ID for OpenAI Sign in with ChatGPT
 * (ext_agent_host_id). Mirrors SettingsManager.getOrCreateDeviceId().
 */
function createSettingsDeviceId(agentDir: string, cwd: string): () => string {
  const settings = SettingsManager.create(cwd, agentDir);
  return () => settings.getOrCreateDeviceId();
}

function buildInteraction(loginId: string, signal: AbortSignal): AuthInteraction {
  return {
    signal,
    notify(event: AuthEvent) {
      // Same event types LoginDialogComponent.notifyAuthDialog handles.
      emitEvent("auth.notify", {
        login_id: loginId,
        event: event as unknown as Record<string, unknown>,
      });
    },
    async prompt(prompt: AuthPrompt): Promise<string> {
      const promptId = randomUUID();
      emitEvent("auth.prompt", {
        login_id: loginId,
        prompt_id: promptId,
        prompt: {
          type: prompt.type,
          message: prompt.message,
          placeholder: "placeholder" in prompt ? prompt.placeholder : undefined,
          options: "options" in prompt ? prompt.options : undefined,
        },
      });
      return await new Promise<string>((resolve, reject) => {
        // Match Pi interactive-mode: reject with exactly "Login cancelled"
        const onAbort = () => {
          pendingPrompts.delete(promptId);
          reject(new Error("Login cancelled"));
        };
        if (signal.aborted) {
          onAbort();
          return;
        }
        signal.addEventListener("abort", onAbort, { once: true });
        const promptSignal = prompt.signal;
        if (promptSignal) {
          if (promptSignal.aborted) {
            signal.removeEventListener("abort", onAbort);
            reject(new Error("Login cancelled"));
            return;
          }
          promptSignal.addEventListener(
            "abort",
            () => {
              pendingPrompts.delete(promptId);
              signal.removeEventListener("abort", onAbort);
              reject(new Error("Login cancelled"));
            },
            { once: true },
          );
        }
        pendingPrompts.set(promptId, {
          resolve: (value) => {
            signal.removeEventListener("abort", onAbort);
            resolve(value);
          },
          reject: (err) => {
            signal.removeEventListener("abort", onAbort);
            reject(err);
          },
        });
      });
    },
  };
}

export function replyAuthPrompt(promptId: string, value: string): boolean {
  const pending = pendingPrompts.get(promptId);
  if (!pending) {
    return false;
  }
  pendingPrompts.delete(promptId);
  pending.resolve(value);
  return true;
}

export function cancelAuthPrompt(promptId: string, reason = "Login cancelled"): boolean {
  const pending = pendingPrompts.get(promptId);
  if (!pending) {
    return false;
  }
  pendingPrompts.delete(promptId);
  pending.reject(new Error(reason));
  return true;
}

export async function runProviderLogin(params: Record<string, unknown>): Promise<unknown> {
  const provider = String(params.provider ?? "").trim();
  const authType = String(params.auth_type ?? "oauth").trim() as "oauth" | "api_key";
  const credentialsDir = String(params.credentials_dir ?? "").trim();
  if (!provider) {
    throw new Error("provider required");
  }
  if (!credentialsDir) {
    throw new Error("credentials_dir required");
  }
  if (authType === "oauth" && !OAUTH_PROVIDERS.has(provider)) {
    throw new Error(
      `Pi 未为 ${provider} 提供 OAuth login（支持：${[...OAUTH_PROVIDERS].join(", ")}）`,
    );
  }

  const loginId = String(params.login_id ?? randomUUID());
  const authPath = ensureAuthFile(credentialsDir);
  // Persist SettingsManager deviceId next to credentials (stable across logins).
  const agentDir =
    String(params.agent_dir ?? "").trim() || path.join(credentialsDir, "pi-agent");
  fs.mkdirSync(agentDir, { recursive: true });
  const modelsPath = materializeModelsJson(undefined, agentDir, credentialsDir);
  const cwd = String(params.cwd ?? "").trim() || process.cwd();
  const getDeviceId = createSettingsDeviceId(agentDir, cwd);

  const controller = new AbortController();
  const runtime = await ModelRuntime.create({
    authPath,
    modelsPath,
    allowModelNetwork: false,
    signal: controller.signal,
  });

  emitEvent("auth.login_started", {
    login_id: loginId,
    provider,
    auth_type: authType,
    // Help UI: OpenAI uses Pi openaiChatGPTOAuth (callback http://127.0.0.1:1455/auth/callback)
    flow:
      provider === "openai"
        ? "openai-chatgpt"
        : provider === "openai-codex"
          ? "openai-codex"
          : authType,
  });

  try {
    // Same call shape as interactive-mode loginProvider().
    const credential = await runtime.login(
      provider,
      authType,
      buildInteraction(loginId, controller.signal),
      {
        getDeviceId,
        agentName: "Harness LCA",
      },
    );
    const auth = readPiAuthFile(authPath);
    return {
      ok: true,
      login_id: loginId,
      provider,
      auth_type: credential.type,
      has_credential: Boolean(auth[provider]),
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    emitEvent("auth.login_failed", { login_id: loginId, provider, message });
    throw err;
  } finally {
    emitEvent("auth.login_finished", { login_id: loginId, provider });
  }
}

export async function runProviderLogout(params: Record<string, unknown>): Promise<unknown> {
  const provider = String(params.provider ?? "").trim();
  const credentialsDir = String(params.credentials_dir ?? "").trim();
  if (!provider || !credentialsDir) {
    throw new Error("provider and credentials_dir required");
  }
  const authPath = ensureAuthFile(credentialsDir);
  const runtime = await ModelRuntime.create({
    authPath,
    allowModelNetwork: false,
  });
  await runtime.logout(provider);
  return { ok: true, provider };
}
