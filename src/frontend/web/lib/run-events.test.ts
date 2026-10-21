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

test("verdicts and end states are shown in Chinese", () => {
  assert.equal(describeEvent({ kind: "review_verdict", node: "a", verdict: "pass" }), "审核结论 — a — 通过");
  assert.equal(describeEvent({ kind: "review_verdict", node: "a", verdict: "fail" }), "审核结论 — a — 退回");
  assert.equal(describeEvent({ kind: "node_end", node: "a", status: "passed" }), "节点结束 — a — 通过");
  assert.equal(describeEvent({ kind: "run_end", status: "completed", reason: "全部节点已通过" }), "运行结束 — 完成：全部节点已通过");
  assert.equal(describeEvent({ kind: "run_end", status: "stopped" }), "运行结束 — 已停止");
  assert.equal(describeEvent({ kind: "node_end", node: "a", status: "failed" }), "节点结束 — a — 失败");
});

test("a submitted turn is never shown as errored (I-32)", () => {
  const e = { kind: "agent_settled", node: "lca-bom", role: "executor", round: 1, submitted: true, error: "503: upstream" };
  assert.equal(eventTone(e), "ok");
  assert.equal(describeEvent(e), "回合结束 — lca-bom · executor · 第 1 轮 — 已提交");
  assert.equal(eventTone({ kind: "agent_settled", submitted: false, error: "x" }), "fail");
});
