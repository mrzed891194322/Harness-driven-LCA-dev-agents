import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { shutdownPiSession } from "./lifecycle.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const runtimeDir = path.resolve(here, "..");

test("shutdownPiSession aborts, emits session_shutdown, then disposes", async () => {
  const calls: string[] = [];
  await shutdownPiSession({
    abort: async () => {
      calls.push("abort");
    },
    extensionRunner: {
      hasHandlers: (event) => event === "session_shutdown",
      emit: async (event) => {
        calls.push(`emit:${(event as { type: string }).type}`);
      },
    },
    dispose: () => {
      calls.push("dispose");
    },
  });
  assert.deepEqual(calls, ["abort", "emit:session_shutdown", "dispose"]);
});

test("shutdownPiSession still disposes when abort throws", async () => {
  const calls: string[] = [];
  await shutdownPiSession({
    abort: async () => {
      throw new Error("boom");
    },
    dispose: () => {
      calls.push("dispose");
    },
  });
  assert.deepEqual(calls, ["dispose"]);
});

function startRuntime() {
  const child = spawn(
    process.execPath,
    ["--import", "tsx", path.join(runtimeDir, "src", "main.ts")],
    {
      cwd: runtimeDir,
      env: { ...process.env, PI_RUNTIME_MOCK: "1" },
      stdio: ["pipe", "pipe", "pipe"],
    },
  );
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => (stdout += String(chunk)));
  child.stderr.on("data", (chunk) => (stderr += String(chunk)));
  const exited = new Promise<{ code: number | null; signal: NodeJS.Signals | null }>((resolve) =>
    child.on("exit", (code, signal) => resolve({ code, signal })),
  );
  return { child, exited, out: () => stdout, err: () => stderr };
}

async function waitFor(check: () => boolean, ms: number): Promise<void> {
  const deadline = Date.now() + ms;
  while (!check()) {
    if (Date.now() > deadline) throw new Error("timed out");
    await new Promise((r) => setTimeout(r, 50));
  }
}

function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => setTimeout(() => reject(new Error(label)), ms)),
  ]);
}

test("runtime exits when stdin closes", { timeout: 30_000 }, async () => {
  const rt = startRuntime();
  try {
    await waitFor(() => rt.out().includes('"ready"'), 20_000);
    rt.child.stdin.write(JSON.stringify({ type: "req", id: "1", method: "runtime.info" }) + "\n");
    await waitFor(() => rt.out().includes('"id":"1"'), 5_000);
    assert.match(rt.out(), /"mode":"mock"/);
    rt.child.stdin.end();
    const result = await withTimeout(rt.exited, 10_000, "runtime did not exit after stdin EOF");
    assert.equal(result.code, 0);
    assert.match(rt.err(), /mode=mock/);
    assert.match(rt.err(), /reason=stdin closed/);
  } finally {
    rt.child.kill("SIGKILL");
  }
});

test("runtime exits cleanly on SIGTERM", { timeout: 30_000, skip: process.platform === "win32" }, async () => {
  const rt = startRuntime();
  try {
    await waitFor(() => rt.out().includes('"ready"'), 20_000);
    rt.child.kill("SIGTERM");
    const result = await withTimeout(rt.exited, 10_000, "runtime did not exit after SIGTERM");
    assert.equal(result.code, 0);
    assert.match(rt.err(), /reason=SIGTERM/);
  } finally {
    rt.child.kill("SIGKILL");
  }
});
