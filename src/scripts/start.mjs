#!/usr/bin/env node
// Prepare the repo, then start the control panel (macOS / Linux / Windows).
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const windows = process.platform === "win32";
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

function reportTimeout(label) {
  const seconds = SYNC_TIMEOUT_MS / 1000;
  console.error(`${label} timed out after ${seconds} seconds.`);
  console.error(MIRROR_HINT);
  process.exit(1);
}

function run(command, args, { timeoutMs, stdio = "inherit" } = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd: root,
      stdio,
      shell: windows,
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

async function runOrExit(command, args, { timeoutMs, timeoutLabel } = {}) {
  const result = await run(command, args, { timeoutMs });
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
await runOrExit("uv", ["sync"], {
  timeoutMs: SYNC_TIMEOUT_MS,
  timeoutLabel: "uv sync",
});

console.log("Syncing Node.js dependencies...");
await runOrExit("npm", ["install"], {
  timeoutMs: SYNC_TIMEOUT_MS,
  timeoutLabel: "npm install",
});

console.log("Starting the control panel...");
await runOrExit("npm", ["run", "dev"]);
