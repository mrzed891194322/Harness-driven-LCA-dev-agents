import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import type { SessionLaunchSpec } from "./types.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const runtimeDir = path.resolve(here, "..");
const fakeServer = path.resolve(runtimeDir, "test", "fake_mcp_server.mjs");
const posixOnly = process.platform === "win32";

function startService(socketPath: string, env: Record<string, string> = {}) {
  const child = spawn(
    process.execPath,
    ["--import", "tsx", path.join(runtimeDir, "src", "main.ts"), "--listen", socketPath],
    { cwd: runtimeDir, env: { ...process.env, ...env }, stdio: ["ignore", "pipe", "pipe"] },
  );
  let stderr = "";
  child.stderr.on("data", (chunk) => (stderr += String(chunk)));
  child.stdout.resume();
  const exited = new Promise<{ code: number | null; signal: NodeJS.Signals | null }>((resolve) =>
    child.on("exit", (code, signal) => resolve({ code, signal })),
  );
  return { child, exited, err: () => stderr };
}

interface Message {
  type: string;
  id?: string;
  ok?: boolean;
  result?: any;
  error?: { message: string };
  event?: string;
  data?: Record<string, unknown>;
}

class Client {
  readonly events: Message[] = [];
  private buffer = "";
  private waiters = new Map<string, (m: Message) => void>();
  private nextId = 1;
  private constructor(private readonly socket: net.Socket) {
    socket.setEncoding("utf8");
    socket.on("data", (chunk: string) => {
      this.buffer += chunk;
      let index: number;
      while ((index = this.buffer.indexOf("\n")) >= 0) {
        const line = this.buffer.slice(0, index);
        this.buffer = this.buffer.slice(index + 1);
        const message = JSON.parse(line) as Message;
        if (message.type === "res" && message.id) this.waiters.get(message.id)?.(message);
        else this.events.push(message);
      }
    });
  }

  static connect(socketPath: string): Promise<Client> {
    return new Promise((resolve, reject) => {
      const socket = net.connect(socketPath);
      socket.once("connect", () => resolve(new Client(socket)));
      socket.once("error", reject);
    });
  }

  async call(method: string, params: Record<string, unknown> = {}): Promise<any> {
    const id = String(this.nextId++);
    const reply = new Promise<Message>((resolve) => this.waiters.set(id, resolve));
    this.socket.write(JSON.stringify({ type: "req", id, method, params }) + "\n");
    const message = await reply;
    if (!message.ok) throw new Error(message.error?.message ?? "error");
    return message.result;
  }

  close(): void {
    this.socket.end();
    this.socket.destroy();
  }
}

async function waitFor(check: () => boolean | Promise<boolean>, ms: number): Promise<boolean> {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    if (await check()) return true;
    await new Promise((r) => setTimeout(r, 100));
  }
  return check();
}

async function connectWhenReady(socketPath: string): Promise<Client> {
  assert.ok(await waitFor(() => fs.existsSync(socketPath), 20_000), "socket never appeared");
  return Client.connect(socketPath);
}

function alive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function spec(dir: string, key: string, mcpPidFile?: string): SessionLaunchSpec {
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
    mcp_bindings: mcpPidFile
      ? { fake: { command: process.execPath, args: [fakeServer, mcpPidFile], timeout_ms: 30_000, exposure: "direct" } }
      : {},
    permission_policy: { allowed_tools: ["read", "mcp__fake__*"], allowed_read_globs: [], allowed_write_globs: [] },
    session_storage: {
      agent_dir: path.join(dir, "agents", key),
      session_file: path.join(dir, "sessions", `${key}.jsonl`),
    },
  };
}

function tmpDir(): string {
  // Short path: Unix socket paths are limited to ~104 bytes.
  return fs.mkdtempSync(path.join(os.tmpdir(), "pirt-"));
}

test(
  "service: many clients share one runtime; a closed connection releases its sessions",
  { timeout: 60_000, skip: posixOnly },
  async () => {
    const dir = tmpDir();
    const socketPath = path.join(dir, "rt.sock");
    const rt = startService(socketPath, { PI_RUNTIME_MOCK: "1" });
    try {
      const a = await connectWhenReady(socketPath);
      const b = await Client.connect(socketPath);
      await a.call("client.hello", { label: "workflow" });
      await b.call("client.hello", { label: "backend" });
      await a.call("session.create", { launch_spec: spec(dir, "s1") });

      const turn = await a.call("session.run_turn", { session_key: "s1", prompt: "hi" });
      assert.equal(turn.status, "ok");
      // turn events go to the connection that asked for the turn only
      assert.ok(await waitFor(() => a.events.some((e) => e.event === "turn.event"), 5_000));
      assert.ok(!b.events.some((e) => e.event === "turn.event" || e.event === "turn.progress"));
      assert.ok(a.events.some((e) => e.event === "ready" && typeof e.data?.pid === "number"));

      const info = await b.call("runtime.info");
      assert.equal(info.transport, "socket");
      assert.equal(info.socket, socketPath);
      assert.equal(info.mode, "mock");
      assert.deepEqual(
        info.connections.map((c: { label: string; sessions: number }) => [c.label, c.sessions]),
        [["workflow", 1], ["backend", 0]],
      );
      assert.equal(info.sessions.length, 1);

      // A second runtime on the same socket refuses to start.
      const second = startService(socketPath, { PI_RUNTIME_MOCK: "1" });
      const result = await second.exited;
      assert.equal(result.code, 1);
      assert.match(second.err(), /已在运行/);

      a.close(); // e.g. workflow.py crashed
      assert.ok(
        await waitFor(async () => (await b.call("runtime.info")).sessions.length === 0, 5_000),
        "sessions of a closed connection must be released",
      );
      // the runtime itself stays up for the other clients
      assert.equal((await b.call("protocol.version")).version, 1);
      b.close();

      rt.child.kill("SIGTERM");
      const exit = await rt.exited;
      assert.equal(exit.code, 0);
      assert.ok(!fs.existsSync(socketPath), "socket removed on shutdown");
      assert.match(rt.err(), /reason=SIGTERM/);
    } finally {
      rt.child.kill("SIGKILL");
      fs.rmSync(dir, { recursive: true, force: true });
    }
  },
);

test(
  "service: session.release_all only touches the caller's sessions",
  { timeout: 60_000, skip: posixOnly },
  async () => {
    const dir = tmpDir();
    const socketPath = path.join(dir, "rt.sock");
    const rt = startService(socketPath, { PI_RUNTIME_MOCK: "1" });
    try {
      const a = await connectWhenReady(socketPath);
      const b = await Client.connect(socketPath);
      await a.call("session.create", { launch_spec: spec(dir, "a1") });
      await b.call("session.create", { launch_spec: spec(dir, "b1") });
      assert.deepEqual(await a.call("session.release_all"), { released: 1 });
      const info = await b.call("runtime.info");
      assert.deepEqual(info.sessions.map((s: { session_key: string }) => s.session_key), ["b1"]);
      a.close();
      b.close();
    } finally {
      rt.child.kill("SIGTERM");
      await rt.exited;
      fs.rmSync(dir, { recursive: true, force: true });
    }
  },
);

test(
  "service: a stale socket file from a killed runtime is replaced",
  { timeout: 30_000, skip: posixOnly },
  async () => {
    const dir = tmpDir();
    const socketPath = path.join(dir, "rt.sock");
    fs.writeFileSync(socketPath, "");
    const rt = startService(socketPath, { PI_RUNTIME_MOCK: "1" });
    try {
      assert.ok(await waitFor(() => rt.err().includes("listening on"), 20_000), rt.err());
      const c = await Client.connect(socketPath);
      assert.equal((await c.call("protocol.version")).version, 1);
      c.close();
    } finally {
      rt.child.kill("SIGTERM");
      await rt.exited;
      fs.rmSync(dir, { recursive: true, force: true });
    }
  },
);

test(
  "service: disconnecting stops the MCP servers of that client's sessions (#22)",
  { timeout: 90_000, skip: posixOnly || process.env.PI_RUNTIME_MOCK === "1" },
  async () => {
    const dir = tmpDir();
    const socketPath = path.join(dir, "rt.sock");
    const env = { ...process.env } as Record<string, string>;
    delete env.PI_RUNTIME_MOCK;
    const rt = startService(socketPath, env);
    try {
      const a = await connectWhenReady(socketPath);
      const pidFile = path.join(dir, "mcp.pid");
      await a.call("session.create", { launch_spec: spec(dir, "real", pidFile) });
      const mcpPid = Number(fs.readFileSync(pidFile, "utf8"));
      assert.ok(alive(mcpPid));
      a.close();
      assert.ok(await waitFor(() => !alive(mcpPid), 15_000), `MCP server ${mcpPid} survived its client`);
      assert.ok(alive(rt.child.pid!), "runtime keeps running");
    } finally {
      rt.child.kill("SIGTERM");
      await rt.exited;
      fs.rmSync(dir, { recursive: true, force: true });
    }
  },
);
