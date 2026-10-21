import test from "node:test";
import assert from "node:assert/strict";
import { isLive, summarizeActivity } from "./run-activity.ts";

test("v5 events become per node.role.round chips", () => {
  const items = summarizeActivity([
    { kind: "turn_start", node: "a", role: "executor", round: 1 },
    { kind: "model_retry", node: "a", role: "executor", round: 1, detail: "1/3 after 10s: 503" },
    { kind: "agent_settled", node: "a", role: "executor", round: 1, submitted: true },
    { kind: "turn_start", node: "a", role: "reviewer", round: 1 },
    { kind: "review_verdict", node: "a", round: 1, verdict: "reject" },
    { kind: "turn_start", node: "a", role: "executor", round: 2 },
  ]);
  assert.equal(items.length, 3);
  assert.equal(items[0].handoff, "ok");
  assert.equal(items[0].retries, 1);
  assert.equal(items[1].verdict, "reject");
  assert.equal(isLive(items[2], true), true);
  assert.equal(isLive(items[2], false), false);
});
