// Derives the openLCA banner from the run's own activity events (no persistence).
// down: latest openlca_unresponsive has no recovery sign after it.
// recovered: a later successful control_openlca tool result, or the run ended.

export type ActivityEvent = {
  kind?: string;
  ts?: string;
  tool?: string;
  summary?: string;
  stage?: string;
};

export type OpenlcaSignal =
  | { state: "ok" }
  | { state: "down"; since: string }
  | { state: "recovered"; since: string };

const ENDED = new Set(["completed", "failed", "interrupted", "aborted", "stopped"]);

function isOpenlcaSuccess(event: ActivityEvent): boolean {
  if (event.kind !== "tool_result") return false;
  if (!(event.tool || "").includes("control_openlca")) return false;
  return /"status"\s*:\s*"success"/.test(event.summary || "");
}

export function foldOpenlcaSignal(previous: OpenlcaSignal, events: ActivityEvent[]): OpenlcaSignal {
  let signal = previous;
  for (const event of events) {
    if (event.kind === "openlca_unresponsive") {
      signal = { state: "down", since: event.ts || "" };
    } else if (signal.state === "down" && isOpenlcaSuccess(event)) {
      signal = { state: "recovered", since: signal.since };
    }
  }
  return signal;
}

export function settleOpenlcaSignal(signal: OpenlcaSignal, runStatus: string): OpenlcaSignal {
  if (signal.state === "down" && ENDED.has(runStatus)) return { state: "recovered", since: signal.since };
  return signal;
}

export function clockLabel(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

export function lastStageFromEvents(previous: string, events: ActivityEvent[]): string {
  let stage = previous;
  for (const event of events) if (event.stage) stage = event.stage;
  return stage;
}
