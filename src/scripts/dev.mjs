#!/usr/bin/env node
// Start the control panel: FastAPI backend, the project's single pi-runtime, and
// the Next.js web. Usually run through `npm start` (syncs dependencies first).
//
//   npm run dev                 detached (Linux/macOS): every service runs in its own
//                               session (setsid), survives the launching shell, pid in
//                               .local/run/<name>.pid, output in .local/logs/<name>.log.
//                               Stop with `npm run stop`.
//   npm run dev -- --foreground stays attached and streams the logs; Ctrl-C stops
//                               exactly what `npm run stop` stops, in the same order.
//
// Start order: backend, then immediately pi-runtime (socket .local/run/pi-runtime.sock,
// PI_RUNTIME_SOCKET overrides), then web. Exactly one pi-runtime per project: the
// backend and every workflow.py run connect to it and never start their own.
//
// Models are real by default. PI_RUNTIME_MOCK=1 (test-only) must be set explicitly.
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import {
  SERVICES,
  alive,
  logDir,
  logFile,
  parseEnvFile,
  pidFile,
  readPid,
  removePid,
  repoProcesses,
  root,
  runtimeArgv,
  runtimeEnv,
  runtimeRequest,
  runtimeSocket,
  sleep,
  socketInUse,
  windows,
  writePid,
} from "./service_files.mjs";
import { stopAll } from "./stop_lib.mjs";

const foreground = process.argv.includes("--foreground") || process.argv.includes("-f");

if (windows) {
  console.error("The pi-runtime service needs Unix domain sockets; run the control panel on Linux/macOS (or WSL).");
  process.exit(1);
}

function resolvePort(fileEnv, key, fallback) {
  const raw = (process.env[key] || fileEnv[key] || fallback).trim();
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    console.error(`${key} is not a valid port: ${raw}`);
    process.exit(1);
  }
  return port;
}

function portFree(port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", (err) => {
      if (err.code === "EADDRINUSE") resolve(false);
      else reject(err);
    });
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(port, "127.0.0.1");
  });
}

const fileEnv = parseEnvFile(path.join(root, ".env"));
const webPort = resolvePort(fileEnv, "GUI_WEB_PORT", "3000");
const apiPort = resolvePort(fileEnv, "GUI_API_PORT", "8800");
const socketPath = runtimeSocket();

if (webPort === apiPort) {
  console.error("GUI_WEB_PORT and GUI_API_PORT must be different.");
  process.exit(1);
}

// Real models unless the caller explicitly asked for the test-only mock.
const mode = process.env.PI_RUNTIME_MOCK === "1" ? "mock" : "real";
console.log(`mode=${mode}`);

// ------------------------------------------------- never stack a second runtime

for (const name of SERVICES) {
  const pid = readPid(name);
  if (pid && alive(pid)) {
    console.error(`${name} is already running (pid ${pid}, ${pidFile(name)}). Run \`npm run stop\` first.`);
    process.exit(1);
  }
  if (pid) removePid(name);
}
if (await socketInUse(socketPath)) {
  console.error(`A pi-runtime is already listening on ${socketPath}. Run \`npm run stop\` first.`);
  process.exit(1);
}
const strayRuntimes = repoProcesses().filter((p) => p.kind === "pi-runtime");
if (strayRuntimes.length) {
  console.error(
    `pi-runtime already running for this checkout (pid ${strayRuntimes.map((p) => p.pid).join(", ")}). Run \`npm run stop\` first.`,
  );
  process.exit(1);
}
if (!(await portFree(apiPort))) {
  console.error(`API port ${apiPort} is already in use. Run \`npm run stop\`, or change GUI_API_PORT in .env.`);
  process.exit(1);
}
if (!(await portFree(webPort))) {
  console.error(`Web port ${webPort} is already in use. Run \`npm run stop\`, or change GUI_WEB_PORT in .env.`);
  process.exit(1);
}
const runtimeCommand = runtimeArgv(socketPath);
if (!runtimeCommand) {
  console.error("pi-runtime is not built: npm install && npm run build -w @harness/pi-runtime");
  process.exit(1);
}

// ------------------------------------------------------------------ services

const pythonPath = [path.join(root, "src"), root, process.env.PYTHONPATH || ""]
  .filter(Boolean)
  .join(path.delimiter);

const sharedEnv = {
  GUI_WEB_PORT: String(webPort),
  GUI_API_PORT: String(apiPort),
  PYTHONPATH: pythonPath,
  PI_RUNTIME_SOCKET: socketPath,
};

const backendEnv = { ...process.env, ...sharedEnv };
if (backendEnv.PI_RUNTIME_PRIVATE) {
  // Test-only switch: it would make backend/workflow.py spawn private runtimes.
  console.warn("ignoring PI_RUNTIME_PRIVATE for the control panel (single shared pi-runtime).");
  delete backendEnv.PI_RUNTIME_PRIVATE;
}

let piEnv;
try {
  // Same whitelist the MCP servers always got (ISSUES #16); computed before the
  // backend starts so the runtime can follow it immediately.
  piEnv = { ...runtimeEnv(backendEnv), PI_RUNTIME_SOCKET: socketPath };
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
delete piEnv.PI_RUNTIME_PRIVATE;

const services = {
  backend: {
    cmd: "uv",
    args: ["run", "uvicorn", "backend.api.app:app", "--app-dir", "src", "--host", "127.0.0.1", "--port", String(apiPort)],
    env: backendEnv,
    url: `http://127.0.0.1:${apiPort}/api/health`,
    timeoutMs: 90_000,
  },
  "pi-runtime": {
    cmd: process.execPath,
    args: runtimeCommand,
    env: piEnv,
    socket: socketPath,
    timeoutMs: 30_000,
  },
  web: {
    cmd: "npm",
    args: ["run", "dev", "-w", "@harness/web"],
    env: { ...process.env, ...sharedEnv, PORT: String(webPort) },
    url: `http://127.0.0.1:${webPort}/`,
    timeoutMs: 120_000,
  },
};

function shown(file) {
  const rel = path.relative(root, file);
  return rel && !rel.startsWith("..") ? rel : file;
}

console.log(`Control panel: web http://127.0.0.1:${webPort}  api http://127.0.0.1:${apiPort}  pi-runtime ${shown(socketPath)}`);

fs.mkdirSync(logDir, { recursive: true });
const started = {};
let stopping = false;

async function stopEverything(code) {
  if (stopping) return;
  stopping = true;
  console.log("Stopping (backend -> pi-runtime -> web)...");
  await stopAll();
  process.exit(code);
}

if (foreground) {
  // Ctrl-C reaches only this process (the services run in their own sessions),
  // so shutdown order and coverage are the same as `npm run stop`.
  process.on("SIGINT", () => void stopEverything(0));
  process.on("SIGTERM", () => void stopEverything(0));
  process.on("SIGHUP", () => void stopEverything(0));
}

async function launch(name) {
  const svc = services[name];
  const log = logFile(name);
  fs.appendFileSync(log, `\n=== ${new Date().toISOString()} start ${name} mode=${mode} ===\n`);
  const out = foreground ? "inherit" : fs.openSync(log, "a");
  // detached: true => setsid(): own session and process group, no controlling
  // terminal, so closing the launching shell (or Ctrl-C) does not hit it directly.
  const child = spawn(svc.cmd, svc.args, {
    cwd: root,
    env: svc.env,
    stdio: ["ignore", out, out],
    detached: true,
  });
  if (!foreground) fs.closeSync(out);
  const failed = await new Promise((resolve) => {
    child.once("error", (error) => resolve(error));
    child.once("spawn", () => resolve(null));
  });
  if (failed) {
    console.error(`Failed to start ${name} (${svc.cmd}): ${failed.message}`);
    await stopEverything(1);
  }
  if (foreground) {
    child.on("exit", (code, signal) => {
      if (stopping) return;
      console.error(`${name} exited unexpectedly (${signal || code}); stopping the rest.`);
      void stopEverything(1);
    });
  } else {
    child.unref();
  }
  writePid(name, child.pid);
  started[name] = child.pid;
  console.log(`${name}: pid ${child.pid}${foreground ? "" : `  log ${path.relative(root, log)}`}`);
}

await launch("backend");
await launch("pi-runtime");
if (!(await waitReady("pi-runtime"))) {
  console.error("Startup failed; stopping what was started.");
  await stopEverything(1);
}
await launch("web");

const results = await Promise.all(["backend", "web"].map((name) => waitReady(name)));
if (!results.every(Boolean)) {
  console.error("Startup failed; see the logs above. Stopping what was started.");
  await stopEverything(1);
}
if (foreground) {
  console.log("Ready. Ctrl-C (or `npm run stop` elsewhere) stops everything.");
} else {
  console.log("Ready. Stop with `npm run stop`.");
  process.exit(0);
}

async function waitReady(name) {
  const svc = services[name];
  const pid = started[name];
  const deadline = Date.now() + svc.timeoutMs;
  while (Date.now() < deadline) {
    if (!alive(pid)) {
      console.error(`${name} exited during startup. Last log lines (${path.relative(root, logFile(name))}):`);
      console.error(tail(logFile(name), 20));
      return false;
    }
    try {
      if (svc.socket) {
        const info = await runtimeRequest(svc.socket, "runtime.info", {}, 3000);
        console.log(`${name}: ready (pid ${info.pid}, mode=${info.mode}, ${shown(svc.socket)})`);
        return true;
      }
      const response = await fetch(svc.url, { redirect: "manual", signal: AbortSignal.timeout(5000) });
      if (response.status < 500) {
        console.log(`${name}: ready (${svc.url} -> ${response.status})`);
        return true;
      }
    } catch {
      // not listening yet
    }
    await sleep(svc.socket ? 200 : 1000);
  }
  console.error(`${name} not ready after ${svc.timeoutMs / 1000}s.`);
  console.error(tail(logFile(name), 20));
  return false;
}

function tail(file, lines) {
  try {
    return fs.readFileSync(file, "utf8").trimEnd().split(/\r?\n/).slice(-lines).join("\n");
  } catch {
    return "";
  }
}
