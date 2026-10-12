#!/usr/bin/env node
// Read-only control-panel status. Does not start or stop anything.
//
//   npm run status
//
// Prints status=ready, status=partial, or status=stopped, then addresses and
// live pids. Exit 0 when the report is written. Exit 3 when a port is invalid.
import path from "node:path";
import { readEndpointFile } from "./endpoint.mjs";
import {
  SERVICES,
  groupAlive,
  parseEnvFile,
  readPid,
  repoProcesses,
  root,
} from "./service_files.mjs";
import { classifyPanel, formatPanelReport, mergeProcesses, panelPort } from "./status_lib.mjs";

function recordedEndpoint() {
  const override = (process.env.PI_RUNTIME_SOCKET || "").trim();
  if (override) return override;
  return readEndpointFile(root) || "";
}

function listPanelProcesses() {
  const fromPidFiles = [];
  for (const name of SERVICES) {
    const pid = readPid(name);
    if (pid && groupAlive(pid)) fromPidFiles.push({ name, pid });
  }
  const strays = repoProcesses()
    .filter((proc) => !fromPidFiles.some((item) => item.pid === proc.pid))
    .map((proc) => ({ name: proc.kind, pid: proc.pid }));
  return mergeProcesses(fromPidFiles, strays);
}

async function apiHealth(port) {
  try {
    const response = await fetch(`http://127.0.0.1:${port}/api/health`, {
      redirect: "manual",
      signal: AbortSignal.timeout(5000),
    });
    if (response.status !== 200) return false;
    const body = await response.json();
    return body?.status === "ok";
  } catch {
    return false;
  }
}

const fileEnv = parseEnvFile(path.join(root, ".env"));
let webPort;
let apiPort;
try {
  webPort = panelPort(process.env.GUI_WEB_PORT || fileEnv.GUI_WEB_PORT, "3000");
  apiPort = panelPort(process.env.GUI_API_PORT || fileEnv.GUI_API_PORT, "8800");
} catch (error) {
  console.error(error.message);
  process.exit(3);
}

const processes = listPanelProcesses();
const healthOk = await apiHealth(apiPort);
const status = classifyPanel(processes, healthOk);
process.stdout.write(
  formatPanelReport({
    status,
    webPort,
    apiPort,
    endpoint: recordedEndpoint(),
    healthOk,
    processes,
  }),
);
