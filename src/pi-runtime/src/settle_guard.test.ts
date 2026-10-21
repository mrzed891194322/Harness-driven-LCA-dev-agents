import { test } from "node:test";
import assert from "node:assert/strict";
import { SettleGuard, settlePolicyOf } from "./settle_guard.js";

const policy = { submit_file: "/x/submit.json", max_nudges: 2, max_turns: 3, timeout_min: 45 };

test("nudges up to max_nudges then lets it settle without submit", () => {
  const g = new SettleGuard(policy, () => false);
  g.begin(() => {});
  const r1 = g.beforeSettle();
  assert.equal(r1?.continue, true);
  assert.equal(r1?.entries?.[0].type, "custom_message");
  assert.equal(g.beforeSettle()?.continue, true);
  assert.equal(g.beforeSettle(), undefined);
  const s = g.summary();
  assert.equal(s.nudges, 2);
  assert.equal(s.submitted, false);
  assert.deepEqual(s.log.map((l) => l.kind), ["nudge", "nudge", "no_submit"]);
  g.clear();
});

test("accepted submit settles without nudge", () => {
  const g = new SettleGuard(policy, () => true);
  g.begin(() => {});
  assert.equal(g.beforeSettle(), undefined);
  assert.equal(g.summary().submitted, true);
  g.clear();
});

test("max_turns aborts once and records the reason", () => {
  let aborted = 0;
  const g = new SettleGuard(policy, () => false);
  g.begin(() => {});
  for (let i = 0; i < 5; i++) g.onTurnEnd(() => (aborted += 1));
  assert.equal(aborted, 1);
  assert.equal(g.summary().abort_reason, "max_turns");
  assert.equal(g.beforeSettle(), undefined);
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

test("policy parsing", () => {
  assert.equal(settlePolicyOf({}), null);
  assert.equal(settlePolicyOf({ settle: { submit_file: "/a", max_nudges: 1 } })?.max_nudges, 1);
});

test("rejections do not spend nudges; max_rejections fails the turn", () => {
  let lines = 0;
  const p = { ...policy, rejections_file: "/x/submit_rejections.jsonl", max_rejections: 3 };
  const g = new SettleGuard(p, () => false, () => lines);
  g.begin(() => {});
  lines = 1;
  assert.equal(g.beforeSettle()?.continue, true); // rejected -> retry reminder
  lines = 2;
  assert.equal(g.beforeSettle()?.continue, true);
  assert.equal(g.summary().nudges, 0);
  lines = 3;
  let aborted = 0;
  g.onTurnEnd(() => aborted++);
  assert.equal(aborted, 1);
  assert.equal(g.beforeSettle(), undefined);
  const s = g.summary();
  assert.equal(s.abort_reason, "too_many_rejections");
  assert.equal(s.rejections, 3);
  assert.ok(s.log.some((e) => e.kind === "rejected_retry"));
  g.clear();
});

test("rejections from earlier rounds count toward the node limit", () => {
  const p = { ...policy, rejections_file: "/x/r.jsonl", max_rejections: 2 };
  const g = new SettleGuard(p, () => false, () => 2);
  g.begin(() => {});
  assert.equal(g.beforeSettle(), undefined);
  assert.equal(g.summary().abort_reason, "too_many_rejections");
  g.clear();
});

test("max_rejections defaults to 5", () => {
  assert.equal(settlePolicyOf({ settle: { submit_file: "/s" } })?.max_rejections, 5);
});
