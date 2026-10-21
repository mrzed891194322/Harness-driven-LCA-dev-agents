import { test } from "node:test";
import assert from "node:assert/strict";
import { runHref } from "./run-link.ts";
import { reviseWorkLocked } from "./revise-lock.ts";
import { initialWorkflow } from "./initial-workflow.ts";

test("plan links to the matching v5 workflow", () => {
  assert.equal(runHref("new"), "/runs?workflow=full-lca");
  assert.equal(runHref("revise"), "/runs?workflow=revise-lca");
});

test("revise mode is unlocked", () => {
  assert.equal(reviseWorkLocked, false);
});

test("?workflow= wins over the latest run when it exists", () => {
  const ids = ["full-lca", "revise-lca"];
  assert.equal(initialWorkflow("full-lca", ids, "full-lca", "revise-lca"), "revise-lca");
  assert.equal(initialWorkflow("full-lca", ids, "full-lca", "nope"), "full-lca");
});
