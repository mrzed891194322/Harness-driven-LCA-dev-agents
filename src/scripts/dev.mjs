#!/usr/bin/env node
// Start the control panel: FastAPI backend + Next.js web.
//
//   npm run dev                 detached (Linux/macOS): each service runs in its own
//                               session (setsid), survives the launching shell, pid in
//                               .local/run/<name>.pid, output in .local/logs/<name>.log.
//                               Stop with `npm run stop`.
//   npm run dev -- --foreground attached to this terminal; Ctrl-C stops both
//                               (always used on Windows).
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
  root,
  sleep,
  windows,
  writePid,
} from "./service_files.mjs";

const foreground = windows || process.argv.includes("--foreground") || process.argv.includes("-f");

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

if (webPort === apiPort) {
  console.error("GUI_WEB_PORT and GUI_API_PORT must be different.");
  process.exit(1);
}

// Real models unless the caller explicitly asked for the test-only mock.
const mode = process.env.PI_RUNTIME_MOCK === "1" ? "mock" : "real";
console.log(`mode=${mode}`);

for (const name of SERVICES) {
  const pid = readPid(name);
  if (pid && alive(pid)) {
    console.error(`${name} is already running (pid ${pid}, ${pidFile(name)}). Run \`npm run stop\` first.`);
    process.exit(1);
  }
  if (pid) removePid(name);
}

if (!(await portFree(apiPort))) {
  console.error(`API port ${apiPort} is already in use. Run \`npm run stop\`, or change GUI_API_PORT in .env.`);
  process.exit(1);
}
if (!(await portFree(webPort))) {
  console.error(`Web port ${webPort} is already in use. Run \`npm run stop\`, or change GUI_WEB_PORT in .env.`);
  process.exit(1);
}

const pythonPath = [path.join(root, "src"), root, process.env.PYTHONPATH || ""]
  .filter(Boolean)
  .join(path.delimiter);

const sharedEnv = {
  GUI_WEB_PORT: String(webPort),
  GUI_API_PORT: String(apiPort),
  PYTHONPATH: pythonPath,
};

const services = {
  backend: {
    cmd: "uv",
    args: ["run", "uvicorn", "backend.api.app:app", "--app-dir", "src", "--host", "127.0.0.1", "--port", String(apiPort)],
    env: sharedEnv,
    url: `http://127.0.0.1:${apiPort}/api/health`,
    timeoutMs: 90_000,
  },
  web: {
    cmd: "npm",
    args: ["run", "dev", "-w", "@harness/web"],
    env: { ...sharedEnv, PORT: String(webPort) },
    url: `http://127.0.0.1:${webPort}/`,
    timeoutMs: 120_000,
  },
};

console.log(`Control panel: web http://127.0.0.1:${webPort}  api http://127.0.0.1:${apiPort}`);

if (foreground) {
  runForeground();
} else {
  await runDetached();
}

// ---------------------------------------------------------------- detached

async function runDetached() {
  fs.mkdirSync(logDir, { recursive: true });
  const started = {};
  for (const name of ["backend", "web"]) {
    const svc = services[name];
    const log = logFile(name);
    fs.appendFileSync(log, `\n=== ${new Date().toISOString()} start ${name} mode=${mode} ===\n`);
    const out = fs.openSync(log, "a");
    // detached: true => setsid(): own session and process group, no controlling
    // terminal, so closing the launching shell does not take the service down.
    const child = spawn(svc.cmd, svc.args, {
      cwd: root,
      env: { ...process.env, ...svc.env },
      stdio: ["ignore", out, out],
      detached: true,
    });
    fs.closeSync(out);
    const failed = await new Promise((resolve) => {
      child.once("error", (error) => resolve(error));
      child.once("spawn", () => resolve(null));
    });
    if (failed) {
      console.error(`Failed to start ${name} (${svc.cmd}): ${failed.message}`);
      await stopStarted(started);
      process.exit(1);
    }
    child.unref();
    writePid(name, child.pid);
    started[name] = child.pid;
    console.log(`${name}: pid ${child.pid}  log ${path.relative(root, log)}`);
  }

  const results = await Promise.all(
    ["backend", "web"].map((name) => waitReady(name, started[name])),
  );
  if (results.every(Boolean)) {
    console.log("Ready. Stop with `npm run stop`.");
    process.exit(0);
  }
  console.error("Startup failed; see the logs above. Stopping what was started.");
  await stopStarted(started);
  process.exit(1);
}

async function waitReady(name, pid) {
  const svc = services[name];
  const deadline = Date.now() + svc.timeoutMs;
  while (Date.now() < deadline) {
    if (!alive(pid)) {
      console.error(`${name} exited during startup. Last log lines (${path.relative(root, logFile(name))}):`);
      console.error(tail(logFile(name), 20));
      return false;
    }
    try {
      const response = await fetch(svc.url, { redirect: "manual", signal: AbortSignal.timeout(5000) });
      if (response.status < 500) {
        console.log(`${name}: ready (${svc.url} -> ${response.status})`);
        return true;
      }
    } catch {
      // not listening yet
    }
    await sleep(1000);
  }
  console.error(`${name} not ready after ${svc.timeoutMs / 1000}s (${svc.url}).`);
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

async function stopStarted(started) {
  for (const [name, pid] of Object.entries(started)) {
    try {
      process.kill(-pid, "SIGTERM");
    } catch {
      // already gone
    }
    removePid(name);
  }
  await sleep(500);
}

// -------------------------------------------------------------- foreground

function runForeground() {
  const children = [];
  let shuttingDown = false;

  function killChild(child) {
    if (child.pid == null) return;
    if (windows) {
      spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
      return;
    }
    if (!child.killed) child.kill("SIGTERM");
  }

  function shutdown(code = 0) {
    if (shuttingDown) return;
    shuttingDown = true;
    for (const child of children) killChild(child);
    setTimeout(() => process.exit(code), 300);
  }

  process.on("SIGINT", () => shutdown(0));
  process.on("SIGTERM", () => shutdown(0));

  for (const name of ["backend", "web"]) {
    const svc = services[name];
    const child = spawn(svc.cmd, svc.args, {
      cwd: root,
      stdio: "inherit",
      env: { ...process.env, ...svc.env },
      shell: windows,
    });
    children.push(child);
    child.on("error", (error) => {
      console.error(`Failed to start ${svc.cmd}: ${error.message}`);
      shutdown(1);
    });
    child.on("exit", (code, signal) => {
      if (shuttingDown || signal) return;
      if (code && code !== 0) shutdown(code);
    });
  }
}
