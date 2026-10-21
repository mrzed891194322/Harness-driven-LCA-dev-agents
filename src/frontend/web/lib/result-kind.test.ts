import { test } from "node:test";
import assert from "node:assert/strict";
import { resultKind } from "./result-kind.ts";

test("previous/ deliverables stay under 最终交付 (no 上一版 tab)", () => {
  assert.equal(resultKind("workspace/artifacts/previous/report/report.md", "previous"), "final");
  assert.equal(resultKind("workspace/artifacts/previous/bom/bom.json"), "final");
  assert.equal(resultKind("workspace/artifacts/report/report.md", "deliverable"), "final");
  assert.equal(resultKind("workspace/runs/lca-bom/status.json"), "intermediate");
});


test("reviewer verdict pass/fail have labels", async () => {
  const { VERDICT_LABEL } = await import("./result-kind.ts");
  assert.equal(VERDICT_LABEL.pass, "通过");
  assert.equal(VERDICT_LABEL.fail, "退回");
});
