// #1 structured activity stream: items from /api/workflow/progress?after_seq=N.
// The /runs components keep their 599ed0a DOM: AgentStream renders the log text built here,
// ActivitySummary consumes the activity events built here.

export type RunItem = {
  seq: number;
  ts?: string;
  kind: "note" | "error" | "assistant_text" | "tool_call" | "tool_result" | "turn_end";
  node?: string;
  rev?: number;
  redo?: number;
  agent?: string;
  attempt?: number;
  model?: string;
  text?: string;
  tool?: string;
  tool_call_id?: string;
  summary?: string;
  is_error?: boolean;
  handoff?: boolean;
};

export type ItemActivity = {
  node: string;
  agent: string;
  attempt: number;
  kind: "tool_call" | "tool_result" | "turn_end";
  tool?: string;
  tool_call_id?: string;
  summary?: string;
  is_error?: boolean;
  handoff?: boolean;
  ts?: string;
};

/** Node title; a redo visit reads "lca-bom（重做 1）". */
export function nodeLabel(node: string, redo = 0): string {
  return redo > 0 ? `${node}（重做 ${redo}）` : node;
}

function clock(ts = ""): string {
  const m = /T(\d{2}:\d{2}:\d{2})/.exec(ts);
  return m ? m[1] : "00:00:00";
}

function tag(item: RunItem, fallbackModel: string): string {
  const worker = (item.model || fallbackModel || "pi").split("/").pop() || "pi";
  const label = nodeLabel(item.node || "", item.redo || 0);
  return `[${label}(${item.agent || ""}#${item.attempt || 0})-${worker.replace(/-/g, "_")}-${clock(item.ts)}]`;
}

function oneLine(text = ""): string {
  return text.replace(/\s+/g, " ").trim();
}

/** Render items in the progress-log text format AgentStream parses. */
export function itemsToLog(items: RunItem[], fallbackModel = ""): string {
  const lines: string[] = [];
  for (const item of items) {
    if (item.kind === "note") {
      lines.push(`[orchestrator-${clock(item.ts)}] ${oneLine(item.text)}`);
      continue;
    }
    if (!item.node || !item.agent) continue;
    const t = tag(item, fallbackModel);
    if (item.kind === "assistant_text") lines.push(`${t}\n${(item.text || "").trim()}`);
    else if (item.kind === "tool_call") lines.push(`${t} → ${item.tool || ""} ${oneLine(item.summary)}`.trimEnd());
    else if (item.kind === "tool_result") {
      const msg = item.is_error && item.summary ? `: ${oneLine(item.summary)}` : "";
      lines.push(`${t} ${item.is_error ? "✗" : "✓"} ${item.tool || ""}${msg}`);
    } else if (item.kind === "error") lines.push(`${t} error: ${oneLine(item.text) || "provider error"}`);
  }
  return lines.length ? `${lines.join("\n")}\n` : "";
}

/** Tool calls/results and turn ends for the 活动概览 chips. */
export function itemsToActivity(items: RunItem[]): ItemActivity[] {
  const out: ItemActivity[] = [];
  for (const item of items) {
    if (item.kind !== "tool_call" && item.kind !== "tool_result" && item.kind !== "turn_end") continue;
    if (!item.node || !item.agent) continue;
    out.push({
      node: nodeLabel(item.node, item.redo || 0),
      agent: item.agent,
      attempt: Number(item.attempt) || 0,
      kind: item.kind,
      tool: item.tool,
      tool_call_id: item.tool_call_id,
      summary: item.summary,
      is_error: item.is_error,
      handoff: item.handoff,
      ts: item.ts,
    });
  }
  return out;
}

export function lastNodeFromItems(previous: string, items: RunItem[]): string {
  let node = previous;
  for (const item of items) if (item.node) node = nodeLabel(item.node, item.redo || 0);
  return node;
}
