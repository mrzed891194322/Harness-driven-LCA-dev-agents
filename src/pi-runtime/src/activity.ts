/**
 * Maps Pi SDK session events to compact `turn.event` records for the host.
 *
 * Kinds: tool_call | tool_result | text | turn_end. Text deltas are coalesced
 * into paragraphs so the host does not get one record per token.
 */

export const SUMMARY_LIMIT = 300;
const ARG_VALUE_LIMIT = 200;
const TEXT_FLUSH_CHARS = 1500;
const BULKY_ARG_KEYS = new Set([
  "content",
  "contents",
  "old_string",
  "new_string",
  "old_text",
  "new_text",
  "patch",
  "diff",
]);

export type ActivityKind = "tool_call" | "tool_result" | "text" | "turn_end";

export interface ActivityEvent {
  session_key: string;
  kind: ActivityKind;
  ts: string;
  tool?: string;
  tool_call_id?: string;
  args?: Record<string, unknown>;
  summary: string;
  is_error?: boolean;
  handoff?: boolean;
  duration_ms?: number;
}

export type ActivityEmit = (event: ActivityEvent) => void;

export function clip(text: string, limit = SUMMARY_LIMIT): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length <= limit ? flat : `${flat.slice(0, limit).trimEnd()}…`;
}

export function isHandoffTool(name: string): boolean {
  return /(^|__|\.)submit_handoff$/.test(name);
}

/** Keep small scalar args; replace bulky text with its length so records stay small. */
export function compactArgs(args: unknown): Record<string, unknown> {
  if (!args || typeof args !== "object" || Array.isArray(args)) {
    return {};
  }
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(args as Record<string, unknown>)) {
    if (value === null || value === undefined) continue;
    if (typeof value === "string") {
      out[key] =
        BULKY_ARG_KEYS.has(key) && value.length > 80
          ? `<${value.length} chars>`
          : clip(value, ARG_VALUE_LIMIT);
    } else if (typeof value === "number" || typeof value === "boolean") {
      out[key] = value;
    } else {
      const json = safeJson(value);
      out[key] = json.length > ARG_VALUE_LIMIT ? `<${json.length} chars json>` : value;
    }
  }
  return out;
}

const PREFERRED_ARG_KEYS = ["command", "cmd", "path", "file_path", "pattern", "query", "url"];

export function argsSummary(args: unknown): string {
  if (!args || typeof args !== "object") {
    return "";
  }
  const record = args as Record<string, unknown>;
  for (const key of PREFERRED_ARG_KEYS) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return clip(value);
    }
  }
  const compact = compactArgs(args);
  return Object.keys(compact).length ? clip(safeJson(compact)) : "";
}

export function resultSummary(result: unknown): string {
  if (result === null || result === undefined) return "";
  if (typeof result === "string") return clip(result);
  if (typeof result === "object") {
    const content = (result as { content?: unknown }).content;
    if (Array.isArray(content)) {
      const text = content
        .map((part) =>
          part && typeof part === "object" && (part as { type?: string }).type === "text"
            ? String((part as { text?: unknown }).text ?? "")
            : "",
        )
        .filter(Boolean)
        .join(" ");
      if (text) return clip(text);
    }
    const message = (result as { message?: unknown }).message;
    if (typeof message === "string") return clip(message);
  }
  return clip(safeJson(result));
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value) ?? "";
  } catch {
    return String(value);
  }
}

type SessionEventLike = {
  type: string;
  [key: string]: any;
};

export class ActivityRelay {
  private buffer = "";
  private readonly started = new Map<string, Record<string, unknown>>();

  constructor(
    private readonly sessionKey: string,
    private readonly emit: ActivityEmit,
    private readonly now: () => Date = () => new Date(),
  ) {}

  handle(ev: SessionEventLike): void {
    if (ev.type === "message_update" && ev.assistantMessageEvent?.type === "text_delta") {
      this.pushText(String(ev.assistantMessageEvent.delta ?? ""));
      return;
    }
    if (ev.type === "message_end") {
      this.flushText();
      return;
    }
    if (ev.type === "tool_execution_start") {
      this.flushText();
      const tool = String(ev.toolName ?? "");
      const args = compactArgs(ev.args);
      this.started.set(String(ev.toolCallId ?? ""), args);
      this.send({
        kind: "tool_call",
        tool,
        tool_call_id: String(ev.toolCallId ?? ""),
        args,
        summary: argsSummary(ev.args),
        ...(isHandoffTool(tool) ? { handoff: true } : {}),
      });
      return;
    }
    if (ev.type === "tool_execution_end") {
      const tool = String(ev.toolName ?? "");
      const callId = String(ev.toolCallId ?? "");
      const args = this.started.get(callId);
      this.started.delete(callId);
      this.send({
        kind: "tool_result",
        tool,
        tool_call_id: callId,
        ...(args ? { args } : {}),
        summary: resultSummary(ev.result),
        is_error: Boolean(ev.isError),
        ...(typeof ev.durationMs === "number" ? { duration_ms: Math.round(ev.durationMs) } : {}),
        ...(isHandoffTool(tool) ? { handoff: true } : {}),
      });
    }
  }

  /** Call once when the turn settles (ok or error). */
  finish(status: "ok" | "error", detail = ""): void {
    this.flushText();
    this.send({ kind: "turn_end", summary: clip(detail), is_error: status === "error" });
  }

  private pushText(delta: string): void {
    if (!delta) return;
    this.buffer += delta;
    const cut = this.buffer.lastIndexOf("\n\n");
    if (cut > 0) {
      this.sendText(this.buffer.slice(0, cut));
      this.buffer = this.buffer.slice(cut + 2);
    } else if (this.buffer.length >= TEXT_FLUSH_CHARS) {
      this.flushText();
    }
  }

  private flushText(): void {
    const text = this.buffer;
    this.buffer = "";
    this.sendText(text);
  }

  private sendText(text: string): void {
    const trimmed = text.trim();
    if (!trimmed) return;
    // Text keeps line breaks (markdown) but is bounded like other summaries.
    const bounded =
      trimmed.length > TEXT_FLUSH_CHARS ? `${trimmed.slice(0, TEXT_FLUSH_CHARS)}…` : trimmed;
    this.send({ kind: "text", summary: bounded });
  }

  private send(event: Omit<ActivityEvent, "session_key" | "ts">): void {
    this.emit({ session_key: this.sessionKey, ts: this.now().toISOString(), ...event });
  }
}
