// Read-only control-panel state. No process is started or stopped here.
// status=ready: backend, pi-runtime, and web are alive, and /api/health is ok.
// status=partial: something is still up, or the API answers without that full set.
// status=stopped: nothing tracked is alive, and the API does not answer.

export const PANEL_SERVICES = ["backend", "pi-runtime", "web"];

/** Kinds stop.mjs would sweep. A leftover here means the panel is not a clean stop. */
export const TRACKED_KINDS = ["orchestrator", "backend", "pi-runtime", "web", "mcp"];

const LABEL = {
  ready: "面板就绪",
  partial: "进程残缺",
  stopped: "没有在运行",
};

export function panelPort(raw, fallback) {
  const text = String(raw ?? "").trim() || fallback;
  const port = Number(text);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`invalid port: ${text}`);
  }
  return port;
}

/** Pid-file entries first, then strays. The same pid is listed once. */
export function mergeProcesses(fromPidFiles, strays) {
  const seen = new Set();
  const merged = [];
  for (const proc of [...fromPidFiles, ...strays]) {
    if (!TRACKED_KINDS.includes(proc.name) || seen.has(proc.pid)) continue;
    seen.add(proc.pid);
    merged.push({ name: proc.name, pid: proc.pid });
  }
  return merged;
}

export function classifyPanel(processes, healthOk) {
  const names = new Set(processes.map((proc) => proc.name));
  if (PANEL_SERVICES.every((name) => names.has(name)) && healthOk) return "ready";
  if (processes.length === 0 && !healthOk) return "stopped";
  return "partial";
}

export function formatPanelReport({ status, webPort, apiPort, endpoint, healthOk, processes }) {
  const lines = [
    `status=${status}`,
    LABEL[status],
    `web=http://127.0.0.1:${webPort}`,
    `api=http://127.0.0.1:${apiPort}`,
    `endpoint=${endpoint || ""}`,
    `health=${healthOk ? "ok" : "down"}`,
  ];
  for (const proc of processes) lines.push(`${proc.name}=${proc.pid}`);
  return `${lines.join("\n")}\n`;
}
