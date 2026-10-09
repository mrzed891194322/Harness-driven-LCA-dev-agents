// Shared by stop.mjs, restart.mjs and `npm run dev -- --foreground` (Ctrl-C):
// stop exactly the same set of processes in the same order.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import {
  STOP_ORDER,
  alive,
  groupAlive,
  readPid,
  removePid,
  repoProcesses,
  root as defaultRoot,
  runtimeSocket,
  sleep,
  socketInUse,
  windows,
} from "./service_files.mjs";

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
  signalPid(pid, signal);
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

/**
 * Stop backend -> pi-runtime -> web (pid files), then sweep this checkout's
 * strays. Returns the number of processes/groups signalled.
 */
export async function stopAll({ dryRun = false, repoRoot = defaultRoot, log = console.log } = {}) {
  let stopped = 0;
  for (const name of STOP_ORDER) {
    const pid = readPid(name);
    if (!pid) continue;
    if (!groupAlive(pid)) {
      if (!dryRun) removePid(name);
      continue;
    }
    if (dryRun) {
      log(`would stop ${name}: process group ${pid}`);
      continue;
    }
    log(`stopping ${name} (process group ${pid})...`);
    if (name === "pi-runtime") {
      // Leader only: it releases every session and closes its MCP children itself.
      signalPid(pid, "SIGTERM");
    } else {
      signalGroup(pid, "SIGTERM");
    }
    if (!(await waitGone(() => groupAlive(pid), GRACE_MS))) {
      log(`${name} still running after ${GRACE_MS / 1000}s; sending SIGKILL`);
      signalGroup(pid, "SIGKILL");
      await waitGone(() => groupAlive(pid), 3000);
    }
    removePid(name);
    stopped += 1;
  }

  // Strays (orphans of older layouts, a runtime started by hand, ...). Workflow
  // and backend first so they release sessions, then runtimes, then the rest.
  const order = ["orchestrator", "backend", "pi-runtime", "web", "mcp"];
  const rest = repoProcesses(repoRoot).sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
  if (dryRun) {
    for (const p of rest) log(`would stop ${p.kind} pid ${p.pid}: ${p.args}`);
    if (!rest.length) log("no stray processes");
    return 0;
  }
  for (const p of rest) {
    if (!alive(p.pid)) continue;
    log(`stopping stray ${p.kind} pid ${p.pid}`);
    signalPid(p.pid, "SIGTERM");
    stopped += 1;
  }
  if (rest.length) {
    await waitGone(() => rest.some((p) => alive(p.pid)), 8000);
    for (const p of rest) {
      if (alive(p.pid)) {
        log(`pid ${p.pid} (${p.kind}) ignored SIGTERM; sending SIGKILL`);
        signalPid(p.pid, "SIGKILL");
      }
    }
  }

  // The runtime removes its socket on exit; clear a stale one left by SIGKILL.
  const socketPath = runtimeSocket();
  if (fs.existsSync(socketPath) && !(await socketInUse(socketPath))) {
    fs.rmSync(socketPath, { force: true });
  }
  return stopped;
}
