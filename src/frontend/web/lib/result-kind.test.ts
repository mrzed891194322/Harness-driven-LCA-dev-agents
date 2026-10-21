import { test } from "node:test";
import assert from "node:assert/strict";
import { resultKind, runLine } from "./result-kind.ts";

test("previous/ deliverables get their own group", () => {
  assert.equal(resultKind("workspace/artifacts/previous/report/report.md", "previous"), "previous");
  assert.equal(resultKind("workspace/artifacts/previous/bom/bom.json"), "previous");
  assert.equal(resultKind("workspace/artifacts/report/report.md", "deliverable"), "final");
  assert.equal(resultKind("workspace/runs/lca-bom/status.json"), "intermediate");
});

test("run line reads current_node", () => {
  assert.equal(runLine({ status: "running", current_node: "lca-bom" }), "状态 running · 当前节点 lca-bom");
  assert.equal(runLine({ status: "idle" }), "");
});
