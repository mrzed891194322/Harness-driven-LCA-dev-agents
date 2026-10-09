#!/usr/bin/env node
// Stop the control panel started by `npm run dev` (ISSUES #15 / #22 / #23).
//
//   npm run stop               SIGTERM each service's process group (pid files in
//                              .local/run/), wait, SIGKILL if needed, then sweep any
//                              pi-runtime / MCP / orchestrator / backend process of
//                              THIS checkout that is still alive (e.g. orphans).
//   npm run stop -- --dry-run  only list what would be stopped.
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import {
  SERVICES,
  alive,
  groupAlive,
  readPid,
  removePid,
  root as defaultRoot,
  sleep,
  windows,
} from "./service_files.mjs";

const dryRun = process.argv.includes("--dry-run");
const rootArg = process.argv.indexOf("--root");
const root = rootArg > 0 ? path.resolve(process.argv[rootArg + 1]) : defaultRoot;
const GRACE_MS = 15_000;

function signalGroup(pid, signal) {
  if (windows) {
    if (signal === "SIGKILL" || signal === "SIGTERM") {
      spawnSync("taskkill", ["/pid", String(pid), "/t", "/f"], { stdio: "ignore" });
    }
    return;
  }
  try {
    process.kill(-pid, signal);
    return;
  } catch {
    // not a group leader (or gone): signal the process itself
  }
  try {
    process.kill(pid, signal);
  } catch {
    // gone
  }
}

function signalPid(pid, signal) {
  try {
    process.kill(pid, signal);
  } catch {
    // gone
  }
}

async function waitGone(check, ms) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    if (!check()) return true;
    await sleep(250);
  }
  return !check();
}

/** Processes of this checkout that must not outlive the control panel. */
function leftovers() {
  if (windows) return [];
  let out = "";
  try {
    out = execFileSync("ps", ["-eo", "pid=,args="], { encoding: "utf8" });
  } catch {
    return [];
  }
  const prefix = root + path.sep;
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
    const ours = args.includes(prefix) || (cwd !== null && (cwd === root || cwd.startsWith(prefix)));
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

let stopped = 0;

for (const name of SERVICES) {
  const pid = readPid(name);
  if (!pid) continue;
  if (!groupAlive(pid)) {
    if (!dryRun) removePid(name);
    continue;
  }
  if (dryRun) {
    console.log(`would stop ${name}: process group ${pid}`);
    continue;
  }
  console.log(`stopping ${name} (process group ${pid})...`);
  signalGroup(pid, "SIGTERM");
  if (!(await waitGone(() => groupAlive(pid), GRACE_MS))) {
    console.log(`${name} still running after ${GRACE_MS / 1000}s; sending SIGKILL`);
    signalGroup(pid, "SIGKILL");
    await waitGone(() => groupAlive(pid), 3000);
  }
  removePid(name);
  stopped += 1;
}

// Orphans: runtimes first (they close their MCP servers on SIGTERM), then the rest.
const order = ["pi-runtime", "orchestrator", "backend", "web", "mcp"];
let rest = leftovers().sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
if (dryRun) {
  for (const p of rest) console.log(`would stop ${p.kind} pid ${p.pid}: ${p.args}`);
  if (!rest.length) console.log("no stray processes");
  process.exit(0);
}
for (const p of rest) {
  if (!alive(p.pid)) continue;
  console.log(`stopping stray ${p.kind} pid ${p.pid}`);
  signalPid(p.pid, "SIGTERM");
  stopped += 1;
}
if (rest.length) {
  await waitGone(() => rest.some((p) => alive(p.pid)), 8000);
  for (const p of rest) {
    if (alive(p.pid)) {
      console.log(`pid ${p.pid} (${p.kind}) ignored SIGTERM; sending SIGKILL`);
      signalPid(p.pid, "SIGKILL");
    }
  }
}

console.log(stopped ? "stopped." : "nothing was running.");
