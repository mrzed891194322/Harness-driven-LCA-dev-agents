#!/usr/bin/env node
// Official entry (`npm start`): sync dependencies, build pi-runtime, then start the
// control panel (`npm run dev`: backend -> the single pi-runtime -> web).
// Extra arguments go to dev.mjs, e.g. `npm start -- --foreground`.
// Stop with `npm run stop`; `npm run restart` = stop + start.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ensureProjectCaches } from "./tool_caches.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const windows = process.platform === "win32";

// A sandbox that can only write inside the checkout turns uv/npm's default caches
// into read-only paths, so `uv sync` / `npm install` fail before anything starts.
ensureProjectCaches(root);
const SYNC_TIMEOUT_MS = 5 * 60 * 1000;
const MIRROR_HINT = "如果你是中国用户，请考虑更换合适的node或uv下载源";

let current = null;

function fail(message) {
  console.error(message);
  process.exit(1);
}

function killProcess(child) {
  if (child?.pid == null) return;
  if (windows) {
    spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
    return;
  }
  child.kill("SIGTERM");
}

// uv sync rewrites uv.lock to whatever index the user configured (a regional
// mirror, for example). Keep that choice on the machine: if the lockfile
// changed only by download host, put the committed PyPI URLs back.
function restoreIndexOnlyLockChange(lockFile, before) {
  if (!before || !fs.existsSync(lockFile)) return;
  const after = fs.readFileSync(lockFile);
  if (before.equals(after)) return;
  const hostsOnly = (buf) =>
    buf.toString("utf8").replaceAll("\r\n", "\n").replace(/https:\/\/[^/\s"']+/g, "https://HOST");
  if (hostsOnly(before) !== hostsOnly(after)) return;
  fs.writeFileSync(lockFile, before);
  console.log("Restored uv.lock download URLs. Keep UV_DEFAULT_INDEX on this machine; do not commit a mirror into the lockfile.");
}

function reportTimeout(label) {
  const seconds = SYNC_TIMEOUT_MS / 1000;
  console.error(`${label} timed out after ${seconds} seconds.`);
  console.error(MIRROR_HINT);
  process.exit(1);
}

function run(command, args, { timeoutMs, stdio = "inherit", env } = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd: root,
      stdio,
      shell: windows,
      env: env ? { ...process.env, ...env } : process.env,
    });
    current = child;
    let settled = false;
    let timer = null;
    const finish = (payload) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      if (current === child) current = null;
      resolve(payload);
    };
    if (timeoutMs) {
      timer = setTimeout(() => {
        killProcess(child);
        finish({ timedOut: true });
      }, timeoutMs);
    }
    child.on("error", (error) => finish({ error }));
    child.on("exit", (code) => finish({ code: code ?? 1 }));
  });
}

async function runOrExit(command, args, { timeoutMs, timeoutLabel, env } = {}) {
  const result = await run(command, args, { timeoutMs, env });
  if (result.timedOut) reportTimeout(timeoutLabel);
  if (result.error) fail(`Failed to run ${command}: ${result.error.message}`);
  if (result.code !== 0) process.exit(result.code ?? 1);
}

process.on("SIGINT", () => killProcess(current));
process.on("SIGTERM", () => killProcess(current));

const nodeMajor = Number(process.versions.node.split(".")[0]);
if (!Number.isInteger(nodeMajor) || nodeMajor < 22) {
  fail(`Node.js 22+ is required. Current version: ${process.version}.`);
}

const uvProbe = await run("uv", ["--version"], { stdio: "ignore" });
if (uvProbe.error || uvProbe.code !== 0) {
  fail("uv was not found. Install it from https://docs.astral.sh/uv/getting-started/installation/");
}

const envPath = path.join(root, ".env");
const examplePath = path.join(root, ".env.example");
if (!fs.existsSync(envPath)) {
  if (!fs.existsSync(examplePath)) {
    fail(".env.example is missing, so .env could not be created.");
  }
  fs.copyFileSync(examplePath, envPath);
  console.log("Copied .env.example to .env.");
}

console.log("Syncing uv dependencies...");
const lockPath = path.join(root, "uv.lock");
const lockBefore = fs.existsSync(lockPath) ? fs.readFileSync(lockPath) : null;
const sync = await run("uv", ["sync"], { timeoutMs: SYNC_TIMEOUT_MS });
restoreIndexOnlyLockChange(lockPath, lockBefore);
if (sync.timedOut) reportTimeout("uv sync");
if (sync.error) fail(`Failed to run uv: ${sync.error.message}`);
if (sync.code !== 0) process.exit(sync.code ?? 1);

console.log("Syncing Node.js dependencies...");
await runOrExit("npm", ["install"], {
  timeoutMs: SYNC_TIMEOUT_MS,
  timeoutLabel: "npm install",
});

// npm 11 sometimes prunes the workspaces' devDependencies on every other
// `npm install` (observed with 11.19); the build needs typescript, so retry once.
if (!fs.existsSync(path.join(root, "node_modules", "typescript", "bin", "tsc"))) {
  console.log("typescript missing after npm install; running npm install again...");
  await runOrExit("npm", ["install"], {
    timeoutMs: SYNC_TIMEOUT_MS,
    timeoutLabel: "npm install",
  });
}

console.log("Building pi-runtime...");
await runOrExit("npm", ["run", "build", "-w", "@harness/pi-runtime"]);

console.log("Starting the control panel...");
await runOrExit("npm", ["run", "dev", "--", ...process.argv.slice(2)]);
