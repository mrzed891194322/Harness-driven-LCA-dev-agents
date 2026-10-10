import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { disposeAllSessions, handleRuntimeMethod, liveSessionCount } from "./session_host.js";
import type { SessionLaunchSpec } from "./types.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const fakeServer = path.resolve(here, "..", "test", "fake_mcp_server.mjs");

function alive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function waitFor(check: () => boolean, ms: number): Promise<boolean> {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    if (check()) return true;
    await new Promise((r) => setTimeout(r, 100));
  }
  return check();
}

function spec(dir: string, key: string, pidFile: string): SessionLaunchSpec {
  return {
    schema_version: 1,
    run_id: "",
    stage_id: "t",
    assignment_id: key,
    role: "executor",
    attempt: 1,
    session_key: key,
    execution_id: key,
    bundle_hash: "h",
    input_snapshot_hash: "h",
    // Local OpenAI-compatible profile: resolvable without credentials or network.
    // No prompt is sent, so nothing is ever called.
    model_profile: {
      profile_id: "fake",
      provider: "fake-local",
      model_id: "fake-model",
      api_type: "openai-completions",
      base_url: "http://127.0.0.1:9/v1",
    },
    system_sections: [{ id: "s", content: "You are a test session.", source_hash: "h" }],
    turn_context: {},
    knowledge_bindings: [],
    resource_bindings: { project_root: dir },
    mcp_bindings: {
      fake: { command: process.execPath, args: [fakeServer, pidFile], timeout_ms: 30_000, exposure: "direct" },
    },
    permission_policy: { allowed_tools: ["read", "mcp__fake__*"], allowed_read_globs: [], allowed_write_globs: [] },
    session_storage: {
      agent_dir: path.join(dir, "agents", key),
      session_file: path.join(dir, "sessions", `${key}.jsonl`),
    },
  };
}

const skip = process.platform === "win32" || process.env.PI_RUNTIME_MOCK === "1";

test("session.release stops the session's MCP server (ISSUES #22)", { skip, timeout: 60_000 }, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pi-rt-release-"));
  try {
    const pidFile = path.join(dir, "a.pid");
    await handleRuntimeMethod("session.create", { launch_spec: spec(dir, "a", pidFile) });
    const pid = Number(fs.readFileSync(pidFile, "utf8"));
    assert.ok(alive(pid), "MCP server should be running while the session is live");
    const res = await handleRuntimeMethod("session.release", { session_key: "a" });
    assert.deepEqual(res, { released: true });
    assert.ok(await waitFor(() => !alive(pid), 10_000), `MCP server ${pid} still alive after release`);
  } finally {
    await disposeAllSessions();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("disposeAllSessions stops every MCP server", { skip, timeout: 60_000 }, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pi-rt-release-"));
  try {
    const pids: number[] = [];
    for (const key of ["b", "c"]) {
      const pidFile = path.join(dir, `${key}.pid`);
      await handleRuntimeMethod("session.create", { launch_spec: spec(dir, key, pidFile) });
      pids.push(Number(fs.readFileSync(pidFile, "utf8")));
    }
    assert.equal(liveSessionCount(), 2);
    assert.ok(pids.every(alive));
    await disposeAllSessions();
    assert.equal(liveSessionCount(), 0);
    assert.ok(await waitFor(() => pids.every((pid) => !alive(pid)), 10_000), "MCP servers survived disposeAllSessions");
  } finally {
    await disposeAllSessions();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("each session gets its own spec_mcp child, released with the session (P5)", { skip, timeout: 60_000 }, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pi-rt-release-"));
  try {
    const pids: number[] = [];
    for (const key of ["s1", "s2"]) {
      const pidFile = path.join(dir, `${key}.pid`);
      const launch = spec(dir, key, pidFile);
      launch.mcp_bindings = {
        spec_mcp: { command: process.execPath, args: [fakeServer, pidFile], timeout_ms: 30_000, exposure: "direct" },
      };
      launch.permission_policy.allowed_tools = ["read", "mcp__spec_mcp__*"];
      await handleRuntimeMethod("session.create", { launch_spec: launch });
      pids.push(Number(fs.readFileSync(pidFile, "utf8")));
    }
    assert.notEqual(pids[0], pids[1], "spec_mcp must not be shared across sessions");
    await handleRuntimeMethod("session.release", { session_key: "s1" });
    assert.ok(await waitFor(() => !alive(pids[0]), 10_000), "released session's spec_mcp still alive");
    assert.ok(alive(pids[1]), "other session's spec_mcp must stay up");
  } finally {
    await disposeAllSessions();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
