// Shared paths and helpers for dev.mjs / stop.mjs (pid files, logs, liveness).
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

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

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ------------------------------------------------------------ pi-runtime

/** Socket of the project's single pi-runtime (PI_RUNTIME_SOCKET overrides). */
export function runtimeSocket(env = process.env) {
  const override = (env.PI_RUNTIME_SOCKET || "").trim();
  return override ? path.resolve(override) : path.join(runDir, "pi-runtime.sock");
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

/** Is a runtime accepting connections on `socketPath`? */
export function socketInUse(socketPath, timeoutMs = 1000) {
  return new Promise((resolve) => {
    if (!fs.existsSync(socketPath)) {
      resolve(false);
      return;
    }
    const probe = net.connect(socketPath);
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
    const socket = net.connect(socketPath);
    let buffer = "";
    const timer = setTimeout(() => finish(new Error(`${method}: timed out`)), timeoutMs);
    function finish(error, value) {
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

/** pi-runtime / MCP / orchestrator / backend / web processes of this checkout. */
export function repoProcesses(repoRoot = root) {
  if (windows) return [];
  const out = spawnSync("ps", ["-eo", "pid=,args="], { encoding: "utf8" }).stdout || "";
  const prefix = repoRoot + path.sep;
  const patterns = [
    { kind: "pi-runtime", re: /pi-runtime[\\/](dist[\\/]main\.js|src[\\/]main\.ts)/ },
    { kind: "orchestrator", re: /src[\\/]scripts[\\/]workflow\.py/ },
    { kind: "mcp", re: /harness[\\/]tools[\\/]mcp[\\/]/ },
    { kind: "backend", re: /backend\.api\.app:app/ },
    { kind: "web", re: /node_modules[\\/]\.bin[\\/]next dev|next[\\/]dist[\\/]bin[\\/]next dev|^next-server\b/ },
  ];
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
    const hit = patterns.find((p) => p.re.test(args));
    if (hit) found.push({ pid, kind: hit.kind, args });
  }
  return found;
}

function cwdOf(pid) {
  try {
    return fs.realpathSync(`/proc/${pid}/cwd`);
  } catch {
    return null;
  }
}
