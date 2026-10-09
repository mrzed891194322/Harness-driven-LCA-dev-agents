// Shared paths and helpers for dev.mjs / stop.mjs (pid files, logs, liveness).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const runDir = path.join(root, ".local", "run");
export const logDir = path.join(root, ".local", "logs");
export const windows = process.platform === "win32";

/** Long-lived services started by dev.mjs. Order matters for stop (web first). */
export const SERVICES = ["web", "backend"];

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
