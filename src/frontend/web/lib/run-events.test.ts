import { test } from "node:test";
import assert from "node:assert/strict";
import { describeEvent, eventTone, isNotable, mergeEvents } from "./run-events.ts";

test("control events are notable with the right tone", () => {
  assert.equal(isNotable({ kind: "nudge" }), true);
  assert.equal(isNotable({ kind: "turn_start" }), false);
  assert.equal(eventTone({ kind: "too_many_rejections" }), "fail");
  assert.equal(eventTone({ kind: "stop_requested" }), "warn");
  assert.equal(eventTone({ kind: "turn_aborted" }), "fail");
  assert.equal(eventTone({ kind: "model_preflight", ok: false }), "fail");
  assert.equal(eventTone({ kind: "node_end", status: "stopped" }), "warn");
});

test("describe includes node, role, round and detail", () => {
  assert.equal(
    describeEvent({ kind: "nudge", node: "lca-bom", role: "executor", round: 2, detail: "no submit yet" }),
    "催交 — lca-bom · executor · 第 2 轮 — no submit yet",
  );
});

test("merge appends and resets when the log shrinks", () => {
  const a = mergeEvents([], 0, { events: [{ kind: "run_start" }], offset: 1 });
  assert.deepEqual([a.events.length, a.offset, a.reset], [1, 1, false]);
  const b = mergeEvents(a.events, 5, { events: [], offset: 2 });
  assert.deepEqual([b.events.length, b.offset, b.reset], [0, 0, true]);
});
