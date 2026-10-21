import { test } from "node:test";
import assert from "node:assert/strict";
import { SettleGuard, settlePolicyOf } from "./settle_guard.js";

const policy = { submit_file: "/x/submit.json", max_nudges: 2, max_turns: 3, timeout_min: 45, max_rejections: 5, model_retry_delays_s: [1, 2] };

test("nudges up to max_nudges then lets it settle without submit", async () => {
  const g = new SettleGuard(policy, () => false);
  g.begin(() => {});
  const r1 = (await g.beforeSettle());
  assert.equal(r1?.continue, true);
  assert.equal(r1?.entries?.[0].type, "custom_message");
  assert.equal((await g.beforeSettle())?.continue, true);
  assert.equal((await g.beforeSettle()), undefined);
  const s = g.summary();
  assert.equal(s.nudges, 2);
  assert.equal(s.submitted, false);
  assert.deepEqual(s.log.map((l) => l.kind), ["nudge", "nudge", "no_submit"]);
  g.clear();
});

test("accepted submit settles without nudge", async () => {
  const g = new SettleGuard(policy, () => true);
  g.begin(() => {});
  assert.equal((await g.beforeSettle()), undefined);
  assert.equal(g.summary().submitted, true);
  g.clear();
});

test("max_turns aborts once and records the reason", async () => {
  let aborted = 0;
  const g = new SettleGuard(policy, () => false);
  g.begin(() => {});
  for (let i = 0; i < 5; i++) g.onTurnEnd(() => (aborted += 1));
  assert.equal(aborted, 1);
  assert.equal(g.summary().abort_reason, "max_turns");
  assert.equal((await g.beforeSettle()), undefined);
  g.clear();
});

test("timeout aborts", async () => {
  let aborted = 0;
  const g = new SettleGuard({ ...policy, timeout_min: 0.0005 }, () => false);
  g.begin(() => (aborted += 1));
  await new Promise((r) => setTimeout(r, 80));
  assert.equal(aborted, 1);
  assert.equal(g.summary().abort_reason, "timeout");
  g.clear();
});

test("policy parsing", async () => {
  assert.equal(settlePolicyOf({}), null);
  assert.equal(settlePolicyOf({ settle: { submit_file: "/a", max_nudges: 1 } })?.max_nudges, 1);
});

test("rejections do not spend nudges; max_rejections fails the turn", async () => {
  let lines = 0;
  const p = { ...policy, rejections_file: "/x/submit_rejections.jsonl", max_rejections: 3 };
  const g = new SettleGuard(p, () => false, () => lines);
  g.begin(() => {});
  lines = 1;
  assert.equal((await g.beforeSettle())?.continue, true); // rejected -> retry reminder
  lines = 2;
  assert.equal((await g.beforeSettle())?.continue, true);
  assert.equal(g.summary().nudges, 0);
  lines = 3;
  let aborted = 0;
  g.onTurnEnd(() => aborted++);
  assert.equal(aborted, 1);
  assert.equal((await g.beforeSettle()), undefined);
  const s = g.summary();
  assert.equal(s.abort_reason, "too_many_rejections");
  assert.equal(s.rejections, 3);
  assert.ok(s.log.some((e) => e.kind === "rejected_retry"));
  g.clear();
});

test("rejections from earlier rounds count toward the node limit", async () => {
  const p = { ...policy, rejections_file: "/x/r.jsonl", max_rejections: 2 };
  const g = new SettleGuard(p, () => false, () => 2);
  g.begin(() => {});
  assert.equal((await g.beforeSettle()), undefined);
  assert.equal(g.summary().abort_reason, "too_many_rejections");
  g.clear();
});

test("max_rejections defaults to 5", async () => {
  assert.equal(settlePolicyOf({ settle: { submit_file: "/s" } })?.max_rejections, 5);
});

test("provider errors retry with waits, no nudge spent, then fail model_error", async () => {
  const waits: number[] = [];
  const g = new SettleGuard({ ...policy, max_turns: 80 }, () => false, () => 0, async (ms) => {
    waits.push(ms);
  });
  g.begin(() => {});
  const err = { stopReason: "error", errorMessage: "Connection error." };
  g.onTurnEnd(() => {}, err);
  assert.equal((await g.beforeSettle())?.continue, true);
  g.onTurnEnd(() => {}, err);
  assert.equal((await g.beforeSettle())?.continue, true);
  g.onTurnEnd(() => {}, err);
  assert.equal(await g.beforeSettle(), undefined);
  const s = g.summary();
  assert.deepEqual(waits, [1000, 2000]);
  assert.equal(s.nudges, 0);
  assert.equal(s.model_errors, 2);
  assert.equal(s.abort_reason, "model_error");
  assert.deepEqual(s.log.map((l) => l.kind), ["model_retry", "model_retry", "abort"]);
  g.clear();
});

test("a good turn after an error goes back to normal nudging", async () => {
  const g = new SettleGuard(policy, () => false, () => 0, async () => {});
  g.begin(() => {});
  g.onTurnEnd(() => {}, { stopReason: "error", errorMessage: "x" });
  await g.beforeSettle();
  g.onTurnEnd(() => {}, { stopReason: "stop" });
  assert.equal((await g.beforeSettle())?.continue, true);
  assert.equal(g.summary().nudges, 1);
  g.clear();
});
