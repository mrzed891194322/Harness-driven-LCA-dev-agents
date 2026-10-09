import assert from "node:assert/strict";
import test from "node:test";
import {
  ActivityRelay,
  argsSummary,
  compactArgs,
  isHandoffTool,
  resultSummary,
  type ActivityEvent,
} from "./activity.js";

function relay() {
  const events: ActivityEvent[] = [];
  const r = new ActivityRelay("k1", (e) => events.push(e), () => new Date("2026-10-09T14:00:00Z"));
  return { r, events };
}

test("tool call and result are emitted with args summary and error flag", () => {
  const { r, events } = relay();
  r.handle({ type: "tool_execution_start", toolCallId: "c1", toolName: "read", args: { path: "a/b.md" } });
  r.handle({
    type: "tool_execution_end",
    toolCallId: "c1",
    toolName: "read",
    isError: true,
    durationMs: 12.4,
    result: { content: [{ type: "text", text: "ENOENT: no such file" }] },
  });
  assert.equal(events.length, 2);
  assert.deepEqual(
    { kind: events[0].kind, tool: events[0].tool, summary: events[0].summary },
    { kind: "tool_call", tool: "read", summary: "a/b.md" },
  );
  assert.equal(events[1].kind, "tool_result");
  assert.equal(events[1].is_error, true);
  assert.equal(events[1].summary, "ENOENT: no such file");
  assert.equal(events[1].duration_ms, 12);
  assert.deepEqual(events[1].args, { path: "a/b.md" });
  assert.equal(events[0].session_key, "k1");
});

test("text deltas are coalesced into paragraphs and flushed before tools", () => {
  const { r, events } = relay();
  for (const d of ["Hel", "lo ", "world"]) {
    r.handle({ type: "message_update", assistantMessageEvent: { type: "text_delta", delta: d } });
  }
  assert.equal(events.length, 0);
  r.handle({ type: "message_update", assistantMessageEvent: { type: "text_delta", delta: "\n\nNext" } });
  assert.deepEqual(events.map((e) => e.summary), ["Hello world"]);
  r.handle({ type: "tool_execution_start", toolCallId: "c2", toolName: "bash", args: { command: "ls" } });
  assert.deepEqual(events.map((e) => e.kind), ["text", "text", "tool_call"]);
  assert.equal(events[1].summary, "Next");
  r.finish("ok");
  assert.equal(events.at(-1)?.kind, "turn_end");
  assert.equal(events.at(-1)?.is_error, false);
});

test("handoff tool is flagged", () => {
  assert.ok(isHandoffTool("mcp__lca_artifacts__submit_handoff"));
  assert.ok(isHandoffTool("submit_handoff"));
  assert.ok(!isHandoffTool("submit_handoff_draft"));
  const { r, events } = relay();
  r.handle({ type: "tool_execution_start", toolCallId: "h", toolName: "mcp__lca_artifacts__submit_handoff", args: { status: "pass" } });
  assert.equal(events[0].handoff, true);
});

test("bulky args are compacted and summaries truncated", () => {
  const big = "x".repeat(5000);
  assert.deepEqual(compactArgs({ path: "f.txt", content: big }), { path: "f.txt", content: "<5000 chars>" });
  assert.ok(argsSummary({ note: big }).length <= 301);
  assert.ok(resultSummary(big).length <= 301);
});
