import assert from "node:assert/strict";
import test from "node:test";
import { initialWorkflow } from "./initial-workflow.ts";

test("latest run's workflow wins after a refresh", () => {
  assert.equal(initialWorkflow("demo-write", ["full-lca", "demo-write"]), "demo-write");
});

test("no run: default full-lca, else first workflow", () => {
  assert.equal(initialWorkflow("", ["demo-write", "full-lca"]), "full-lca");
  assert.equal(initialWorkflow(undefined, ["demo-write"]), "demo-write");
});

test("a run whose workflow no longer exists falls back", () => {
  assert.equal(initialWorkflow("gone", ["demo-write", "full-lca"]), "full-lca");
});

test("workflow list not loaded yet: trust the run", () => {
  assert.equal(initialWorkflow("demo-write", []), "demo-write");
});
