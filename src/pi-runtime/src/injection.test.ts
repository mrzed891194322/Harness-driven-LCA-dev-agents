import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { redact, knownSecrets, REDACTED } from "./injection.js";
import { disposeAllSessions, handleRuntimeMethod } from "./session_host.js";
import type { SessionLaunchSpec } from "./types.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const fakeServer = path.resolve(here, "..", "test", "fake_mcp_server.mjs");
const FAKE_SECRET = "sk-FAKEinjectiontestSECRET0123456789";
const FAKE_SIGNING = "fake-signing-key-ABCDEF0123456789";

function spec(dir: string, key: string): SessionLaunchSpec {
  return {
    schema_version: 1,
    run_id: "selfcheck",
    stage_id: "t",
    assignment_id: key,
    role: "executor",
    attempt: 1,
    session_key: key,
    execution_id: key,
    bundle_hash: "h",
    input_snapshot_hash: "h",
    model_profile: {
      profile_id: "fake",
      provider: "fake-local",
      model_id: "fake-model",
      api_type: "openai-completions",
      base_url: "http://127.0.0.1:9/v1",
    },
    system_sections: [{ id: "s", content: "You are an injection self-check session.", source_hash: "h" }],
    turn_context: {},
    knowledge_bindings: [],
    resource_bindings: { project_root: dir },
    mcp_bindings: {
      fake: {
        command: process.execPath,
        args: [fakeServer, path.join(dir, "fake.pid")],
        env: { SPEC_MCP_SIGNING_KEY: FAKE_SIGNING, OTHER_TOKEN: FAKE_SECRET },
        timeout_ms: 30_000,
        exposure: "direct",
      },
    },
    permission_policy: { allowed_tools: ["read", "mcp__fake__*"], allowed_read_globs: [], allowed_write_globs: [] },
    session_storage: {
      agent_dir: path.join(dir, "agents", key),
      session_file: path.join(dir, "sessions", `${key}.jsonl`),
    },
  };
}

test("redact removes sensitive keys, known values and token patterns", () => {
  process.env.HARNESS_TEST_API_KEY = FAKE_SECRET;
  try {
    const out = redact(
      { api_key: "abc", nested: { text: `use ${FAKE_SECRET} or Bearer abcdefghijklmnop` }, list: [FAKE_SECRET] },
      knownSecrets(),
    );
    assert.equal(out.api_key, REDACTED);
    assert.ok(!JSON.stringify(out).includes(FAKE_SECRET));
    assert.ok(!JSON.stringify(out).includes("abcdefghijklmnop"));
  } finally {
    delete process.env.HARNESS_TEST_API_KEY;
  }
});

const skip = process.platform === "win32" || process.env.PI_RUNTIME_MOCK === "1";

test("empty-session self-check: effective state comes from the SDK, secrets redacted", { skip, timeout: 60_000 }, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pi-rt-inj-"));
  process.env.HARNESS_TEST_TOKEN = FAKE_SECRET;
  try {
    const res = (await handleRuntimeMethod("session.create", { launch_spec: spec(dir, "inj") })) as any;
    const eff = res.effective;
    assert.equal(eff.captured, true);
    assert.ok(eff.system_prompt.includes("You are an injection self-check session."));
    assert.equal(eff.model.provider, "fake-local");
    assert.equal(eff.model.model_id, "fake-model");
    assert.equal(eff.guard_hook_mounted, true);
    assert.equal(eff.first_request_hook, true);
    assert.ok(eff.mcp_servers.fake.tools.length > 0, "MCP tools registered");
    assert.deepEqual(eff.mcp_servers.fake.exposures, ["direct"]);
    assert.ok(eff.tools.every((t: any) => typeof t.schema_hash === "string"));
    assert.deepEqual(eff.mcp_config.servers.fake.env_names, ["OTHER_TOKEN", "SPEC_MCP_SIGNING_KEY"]);
    const text = JSON.stringify(eff);
    assert.ok(!text.includes(FAKE_SECRET) && !text.includes(FAKE_SIGNING), "secret leaked into effective");
    const again = (await handleRuntimeMethod("session.inspect", { session_key: "inj" })) as any;
    assert.equal(again.effective.system_prompt_hash, eff.system_prompt_hash);
  } finally {
    delete process.env.HARNESS_TEST_TOKEN;
    await disposeAllSessions();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("first provider request payload is captured (dead endpoint, no real model)", { skip, timeout: 90_000 }, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pi-rt-inj1-"));
  try {
    await handleRuntimeMethod("session.create", { launch_spec: spec(dir, "inj1") });
    const run = handleRuntimeMethod("session.run_turn", { session_key: "inj1", prompt: "hi" }).catch(() => null);
    const file = path.join(dir, ".local", "runs", "selfcheck", "sessions", "t.executor.1", "injection", "first_request.json");
    const deadline = Date.now() + 60_000;
    while (!fs.existsSync(file) && Date.now() < deadline) await new Promise((r) => setTimeout(r, 100));
    await handleRuntimeMethod("session.cancel", { session_key: "inj1" }).catch(() => null);
    await Promise.race([run, new Promise((r) => setTimeout(r, 5_000))]);
    const rec = JSON.parse(fs.readFileSync(file, "utf8"));
    assert.equal(rec.captured, true);
    assert.equal(rec.system_prompt_found, true);
    assert.ok(rec.tool_names.some((n: string) => n.startsWith("mcp__fake__")));
    assert.ok(!JSON.stringify(rec).includes(FAKE_SIGNING));
  } finally {
    await disposeAllSessions();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
