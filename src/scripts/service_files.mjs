// Shared paths and helpers for dev.mjs / stop.mjs (pid files, logs, liveness).
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  connectEndpoint,
  isTcpEndpoint,
  parseListenEndpoint,
  readEndpointFile,
  writeEndpointFile,
} from "./endpoint.mjs";
import { matchRepoProcess, parseWin32ProcessList } from "./platform.mjs";

export { allocateLoopbackPort, endpointFile, readEndpointFile, writeEndpointFile } from "./endpoint.mjs";
export { findGitBash, prependPath } from "./platform.mjs";

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const runDir = path.join(root, ".local", "run");
export const logDir = path.join(root, ".local", "logs");
export const windows = process.platform === "win32";

/**
 * Long-lived services started by dev.mjs, in start order: backend, then right
 * away the project's single pi-runtime, then web.
 */
export const SERVICES = ["backend", "pi-runtime", "web"];

/**
 * Stop order (stop.mjs and Ctrl-C in --foreground): backend first -- its lifespan
 * and its workflow.py children release their sessions/MCP while the runtime is
 * still up -- then pi-runtime (disposes whatever is left), then web.
 */
export const STOP_ORDER = ["backend", "pi-runtime", "web"];

export function pidFile(name) {
  return path.join(runDir, `${name}.pid`);
}

export function logFile(name) {
  return path.join(logDir, `${name}.log`);
}

export function readPid(name) {
  try {
    const pid = Number(fs.readFileSync(pidFile(name), "utf8").trim());
    return Number.isInteger(pid) && pid > 0 ? pid : null;
  } catch {
    return null;
  }
}

export function writePid(name, pid) {
  fs.mkdirSync(runDir, { recursive: true });
  fs.writeFileSync(pidFile(name), `${pid}\n`, "utf8");
}

export function removePid(name) {
  fs.rmSync(pidFile(name), { force: true });
}

export function alive(pid) {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === "EPERM";
  }
}

/** Is any process left in process group `pgid`? */
export function groupAlive(pgid) {
  if (windows) return alive(pgid);
  try {
    process.kill(-pgid, 0);
    return true;
  } catch (error) {
    return error.code === "EPERM";
  }
}

export function parseEnvFile(filePath) {
  const parsed = {};
  if (!fs.existsSync(filePath)) return parsed;
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const eq = line.indexOf("=");
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    parsed[key] = value;
  }
  return parsed;
}


/** Flat env-style keys from repo-root config.toml (replaces .env). */
const CONFIG_FLAT_MAP = {
  web_port: "GUI_WEB_PORT",
  api_port: "GUI_API_PORT",
  port: "GUI_PORT",
  lang: "GUI_LANG",
  ipc_host: "OPENLCA_IPC_HOST",
  ipc_port: "OPENLCA_IPC_PORT",
  project_category: "OPENLCA_PROJECT_CATEGORY",
  language: "HARNESS_LANGUAGE",
  agent: "HARNESS_AGENT",
  model: "PI_MODEL",
  model_retry_delays_s: "PI_MODEL_RETRY_DELAYS_S",
};

const SECTION_FLAT = {
  gui: true,
  openlca: true,
  harness: true,
  pi: true,
};

export function parseTomlFlat(text) {
  const parsed = {};
  let section = "";
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const sec = line.match(/^\[([A-Za-z0-9_]+)\]$/);
    if (sec) {
      section = sec[1];
      continue;
    }
    const eq = line.indexOf("=");
    if (eq < 0 || !SECTION_FLAT[section]) continue;
    const field = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, "\\");
    }
    const flat = CONFIG_FLAT_MAP[field];
    if (flat) parsed[flat] = value;
  }
  return parsed;
}

export function loadConfigFlat(repoRoot = root) {
  const configPath = path.join(repoRoot, "config.toml");
  const examplePath = path.join(repoRoot, "config.example.toml");
  if (!fs.existsSync(configPath)) {
    if (fs.existsSync(examplePath)) {
      fs.copyFileSync(examplePath, configPath);
    } else {
      return {};
    }
  }
  return parseTomlFlat(fs.readFileSync(configPath, "utf8"));
}


export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ------------------------------------------------------------ pi-runtime

/**
 * Where the project's single pi-runtime listens.
 * `PI_RUNTIME_SOCKET` wins; otherwise `.local/run/pi-runtime.endpoint`;
 * otherwise the Unix socket `.local/run/pi-runtime.sock`.
 */
export function runtimeSocket(env = process.env, repoRoot = root) {
  const override = (env.PI_RUNTIME_SOCKET || "").trim();
  if (override) return normalizeEndpoint(override);
  const recorded = readEndpointFile(repoRoot);
  if (recorded) return normalizeEndpoint(recorded);
  return path.join(repoRoot, ".local", "run", "pi-runtime.sock");
}

function normalizeEndpoint(value) {
  const parsed = parseListenEndpoint(value);
  return parsed.kind === "tcp" ? parsed.raw : path.resolve(parsed.path);
}

/** node argv for the runtime service (built dist, else tsx on the sources). */
export function runtimeArgv(socketPath) {
  const rt = path.join(root, "src", "pi-runtime");
  const dist = path.join(rt, "dist", "main.js");
  if (fs.existsSync(dist)) return [dist, "--listen", socketPath];
  for (const base of [rt, root]) {
    const tsx = path.join(base, "node_modules", "tsx", "dist", "esm", "index.js");
    if (fs.existsSync(tsx)) return ["--import", tsx, path.join(rt, "src", "main.ts"), "--listen", socketPath];
  }
  return null;
}

/**
 * The runtime's environment: the same whitelist the Python side uses for MCP
 * servers (backend/pi_client/env.py, ISSUES #16), computed by that module.
 */
export function runtimeEnv(baseEnv) {
  const result = spawnSync("uv", ["run", "--no-sync", "python", "-m", "backend.pi_client.env", root], {
    cwd: root,
    env: baseEnv,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(`could not compute pi-runtime env: ${(result.stderr || result.error?.message || "").trim()}`);
  }
  const lines = result.stdout.trim().split(/\r?\n/);
  return JSON.parse(lines[lines.length - 1]);
}

/** Is a runtime accepting connections on this unix path or `tcp://` address? */
export function socketInUse(socketPath, timeoutMs = 1000) {
  return new Promise((resolve) => {
    if (!isTcpEndpoint(socketPath) && !fs.existsSync(socketPath)) {
      resolve(false);
      return;
    }
    let probe;
    try {
      probe = connectEndpoint(socketPath);
    } catch {
      resolve(false);
      return;
    }
    const done = (value) => {
      probe.destroy();
      resolve(value);
    };
    probe.setTimeout(timeoutMs, () => done(false));
    probe.once("connect", () => done(true));
    probe.once("error", () => done(false));
  });
}

/** Send one NDJSON request to the runtime and return its result (or throw). */
export function runtimeRequest(socketPath, method, params = {}, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    let socket;
    try {
      socket = connectEndpoint(socketPath);
    } catch (error) {
      reject(error);
      return;
    }
    let buffer = "";
    let settled = false;
    const timer = setTimeout(() => finish(new Error(`${method}: timed out`)), timeoutMs);
    function finish(error, value) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      socket.destroy();
      if (error) reject(error);
      else resolve(value);
    }
    socket.setEncoding("utf8");
    socket.once("error", (error) => finish(error));
    socket.once("connect", () => {
      socket.write(JSON.stringify({ type: "req", id: "1", method, params }) + "\n");
    });
    socket.on("data", (chunk) => {
      buffer += chunk;
      let index;
      while ((index = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, index);
        buffer = buffer.slice(index + 1);
        let message;
        try {
          message = JSON.parse(line);
        } catch {
          continue;
        }
        if (message.type === "res" && message.id === "1") {
          if (message.ok) finish(null, message.result);
          else finish(new Error(message.error?.message || "runtime error"));
        }
      }
    });
  });
}

/** Ask a running runtime to release sessions and exit. False if it does not answer. */
export function requestRuntimeShutdown(endpoint, timeoutMs = 5000) {
  return runtimeRequest(endpoint, "runtime.shutdown", {}, timeoutMs)
    .then(() => true)
    .catch(() => false);
}

/** pi-runtime / MCP / orchestrator / backend / web processes of this checkout. */
export function repoProcesses(repoRoot = root) {
  if (windows) return windowsRepoProcesses(repoRoot);
  const out = spawnSync("ps", ["-eo", "pid=,args="], { encoding: "utf8" }).stdout || "";
  const prefix = repoRoot + path.sep;
  const found = [];
  for (const line of out.split("\n")) {
    const match = line.trim().match(/^(\d+)\s+(.*)$/);
    if (!match) continue;
    const pid = Number(match[1]);
    const args = match[2];
    if (pid === process.pid) continue;
    const cwd = cwdOf(pid);
    const ours = args.includes(prefix) || (cwd !== null && (cwd === repoRoot || cwd.startsWith(prefix)));
    if (!ours) continue;
    const kind = matchRepoProcess(args);
    if (kind) found.push({ pid, kind, args });
  }
  return found;
}

function windowsRepoProcesses(repoRoot) {
  const script = [
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
    "Get-CimInstance Win32_Process | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress",
  ].join("; ");
  const result = spawnSync(
    "powershell.exe",
    ["-NoProfile", "-NonInteractive", "-Command", script],
    { encoding: "utf8", windowsHide: true },
  );
  if (result.status !== 0) return [];
  return parseWin32ProcessList(result.stdout, repoRoot, process.pid);
}

function cwdOf(pid) {
  try {
    return fs.realpathSync(`/proc/${pid}/cwd`);
  } catch {
    return null;
  }
}
