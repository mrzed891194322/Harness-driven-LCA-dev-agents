import { test } from "node:test";
import assert from "node:assert/strict";
import { fieldRows, rawLines } from "./harness-view.ts";

test("fields render as rows", () => {
  const rows = fieldRows({ title: "红线", enabled: true, applies_to: ["executor", "reviewer"], prompt: "a\nb", deliver: { max_nudges: 2 } });
  assert.deepEqual(rows[0], ["title", "红线", false]);
  assert.deepEqual(rows[1], ["enabled", "true", false]);
  assert.deepEqual(rows[2], ["applies_to", "executor、reviewer", false]);
  assert.equal(rows[3][2], true);
  assert.equal(rows[4][1], JSON.stringify({ max_nudges: 2 }, null, 2));
  assert.deepEqual(fieldRows(null), []);
});

test("raw lines flag the error line", () => {
  const lines = rawLines("a: 1\nb: [\n", 2);
  assert.deepEqual(lines.map((l) => l.bad), [false, true]);
  assert.equal(lines.length, 2);
});
