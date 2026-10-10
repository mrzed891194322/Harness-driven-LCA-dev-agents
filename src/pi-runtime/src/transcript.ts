/**
 * transcript.jsonl: the full record of one Pi session, exported by the runtime from
 * the SDK's own session file (SessionManager JSONL) plus what only the live event
 * stream knows (turn timing, auto-retries, turn errors). Never rebuilt from events.jsonl.
 *
 * One JSON object per line, `type` is one of:
 *   header | system | message | tool_result | entry | turn | retry | summary
 * A record whose JSON exceeds BLOB_LIMIT is stored whole in transcript.blobs/<n>.json and
 * replaced by a stub carrying `blob` (relative path) and `bytes`.
 */
import fs from "node:fs";
import path from "node:path";
import type { SessionLaunchSpec } from "./types.js";
import { knownSecrets, redact, sessionSnapshotDir, sha256 } from "./injection.js";

export const BLOB_LIMIT = 1024 * 1024;

export interface TurnRecord {
  type: "turn";
  index: number;
  started_at: string;
  ended_at?: string;
  latency_ms?: number;
  status: "running" | "ok" | "error" | "aborted";
  error?: string;
  prompt_sha256: string;
}

export interface RetryRecord {
  type: "retry";
  ts: string;
  phase: "start" | "end";
  attempt?: number;
  max_attempts?: number;
  delay_ms?: number;
  error?: string;
  success?: boolean;
}

export interface TranscriptState {
  createdAt: number;
  turns: TurnRecord[];
  retries: RetryRecord[];
}

function readJsonl(file: string): any[] {
  if (!file || !fs.existsSync(file)) return [];
  const out: any[] = [];
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    if (!line.trim()) continue;
    try {
      out.push(JSON.parse(line));
    } catch {
      out.push({ type: "unparsable_line", text: line.slice(0, 2000) });
    }
  }
  return out;
}

function textOf(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .filter((c: any) => c?.type === "text")
    .map((c: any) => String(c.text ?? ""))
    .join("");
}

function usageOf(u: any) {
  if (!u) return null;
  return {
    input: u.input ?? 0,
    output: u.output ?? 0,
    cache_read: u.cacheRead ?? 0,
    cache_write: u.cacheWrite ?? 0,
    reasoning: u.reasoning ?? null,
    total: u.totalTokens ?? (u.input ?? 0) + (u.output ?? 0) + (u.cacheRead ?? 0) + (u.cacheWrite ?? 0),
    cost_total: u.cost?.total ?? null,
  };
}

function convert(entry: any, sinceMs: number): any {
  const ts = entry.timestamp ?? null;
  const scope = ts && Date.parse(ts) < sinceMs ? "earlier_attempt" : "this_attempt";
  if (entry.type === "session") return { type: "header", ...entry };
  if (entry.type !== "message") return { type: "entry", entry_type: entry.type, ts, scope, raw: entry };
  const m = entry.message ?? {};
  const base = { id: entry.id, parent_id: entry.parentId ?? null, ts, scope };
  if (m.role === "assistant") {
    const content = Array.isArray(m.content) ? m.content : [];
    return {
      type: "message",
      role: "assistant",
      ...base,
      provider: m.provider ?? null,
      model: m.model ?? null,
      response_model: m.responseModel ?? null,
      api: m.api ?? null,
      text: content.filter((c: any) => c.type === "text").map((c: any) => c.text).join(""),
      thinking: content
        .filter((c: any) => c.type === "thinking")
        .map((c: any) => (c.redacted ? { redacted: true } : { text: c.thinking })),
      tool_calls: content
        .filter((c: any) => c.type === "toolCall")
        .map((c: any) => ({ id: c.id, name: c.name, arguments: c.arguments })),
      usage: usageOf(m.usage),
      latency_ms: m.durationMs ?? null,
      stop_reason: m.stopReason ?? null,
      error: m.errorMessage ?? null,
      thinking_level: m.thinkingLevel ?? null,
    };
  }
  if (m.role === "toolResult") {
    return {
      type: "tool_result",
      ...base,
      tool_call_id: m.toolCallId,
      tool_name: m.toolName,
      is_error: Boolean(m.isError),
      duration_ms: m.durationMs ?? null,
      text: textOf(m.content),
      content: (m.content ?? []).filter((c: any) => c.type !== "text"),
      details: m.details ?? null,
      nested_calls: m.nestedCalls ?? null,
    };
  }
  return { type: "message", role: m.role ?? "unknown", ...base, text: textOf(m.content), raw: m };
}

function readHandoff(spec: SessionLaunchSpec): unknown {
  const rel = spec.handoff_binding?.relative_path;
  if (!rel) return null;
  const root = spec.resource_bindings.project_root ?? process.cwd();
  const file = path.isAbsolute(rel) ? rel : path.join(root, rel);
  try {
    const h = JSON.parse(fs.readFileSync(file, "utf8"));
    return { path: rel, status: h.status ?? null, status_reason: h.status_reason ?? null, role: h.role ?? null };
  } catch {
    return { path: rel, status: null, missing: true };
  }
}

/** Write transcript.jsonl (+ blobs) for this session's snapshot dir. Returns its path. */
export function exportTranscript(
  spec: SessionLaunchSpec,
  sessionFile: string,
  systemPrompt: string,
  state: TranscriptState,
  final = false,
): string {
  const dir = sessionSnapshotDir(spec);
  const blobs = path.join(dir, "transcript.blobs");
  fs.mkdirSync(dir, { recursive: true });
  const secrets = knownSecrets(spec);
  const records: any[] = [];
  const entries = readJsonl(sessionFile);
  records.push({
    type: "system",
    source: "pi-sdk session.systemPrompt",
    text: systemPrompt,
    sha256: sha256(systemPrompt),
  });
  const converted = entries.map((e) => convert(e, state.createdAt));
  const header = converted.findIndex((r) => r.type === "header");
  if (header >= 0) records.unshift(converted.splice(header, 1)[0]);
  records.push(...converted, ...state.turns, ...state.retries);

  const totals = { input: 0, output: 0, cache_read: 0, cache_write: 0, total: 0 };
  const thisAttempt = { input: 0, output: 0, cache_read: 0, cache_write: 0, total: 0 };
  let assistant = 0;
  let toolCalls = 0;
  let toolErrors = 0;
  const models = new Set<string>();
  for (const r of converted) {
    if (r.type === "message" && r.role === "assistant") {
      assistant += 1;
      toolCalls += r.tool_calls.length;
      if (r.provider || r.model) models.add(`${r.provider}/${r.model}`);
      for (const bucket of r.scope === "this_attempt" ? [totals, thisAttempt] : [totals]) {
        for (const k of Object.keys(bucket) as Array<keyof typeof bucket>) bucket[k] += Number(r.usage?.[k] ?? 0);
      }
    }
    if (r.type === "tool_result" && r.is_error) toolErrors += 1;
  }
  records.push({
    type: "summary",
    final,
    exported_at: new Date().toISOString(),
    session_key: spec.session_key,
    stage: spec.stage_id,
    role: spec.role,
    attempt: spec.attempt,
    pi_session_file: sessionFile,
    entries: entries.length,
    assistant_messages: assistant,
    tool_calls: toolCalls,
    tool_errors: toolErrors,
    turns: state.turns.length,
    retries: state.retries.filter((r) => r.phase === "start").length,
    models: [...models],
    tokens_total: totals,
    tokens_this_attempt: thisAttempt,
    handoff: readHandoff(spec),
  });

  const lines: string[] = [];
  let blobIndex = 0;
  for (const raw of records) {
    const rec = redact(raw, secrets);
    let line = JSON.stringify(rec);
    if (Buffer.byteLength(line, "utf8") > BLOB_LIMIT) {
      blobIndex += 1;
      fs.mkdirSync(blobs, { recursive: true });
      const name = `${String(blobIndex).padStart(4, "0")}.json`;
      fs.writeFileSync(path.join(blobs, name), line, "utf8");
      const stub: Record<string, unknown> = { type: rec.type, blob: `transcript.blobs/${name}`, bytes: Buffer.byteLength(line, "utf8") };
      for (const k of ["id", "role", "ts", "scope", "tool_call_id", "tool_name", "is_error", "provider", "model", "usage", "stop_reason"]) {
        if (k in rec) stub[k] = (rec as any)[k];
      }
      if (rec.type === "message" && Array.isArray(rec.tool_calls)) {
        stub.tool_calls = rec.tool_calls.map((c: any) => ({ id: c.id, name: c.name }));
      }
      line = JSON.stringify(stub);
    }
    lines.push(line);
  }
  const file = path.join(dir, "transcript.jsonl");
  const tmp = `${file}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, lines.join("\n") + "\n", "utf8");
  fs.renameSync(tmp, file);
  return file;
}
