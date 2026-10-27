import { test } from "node:test";
import assert from "node:assert/strict";
import { resultKind } from "./result-kind.ts";

test("最终交付 only BOM / LCI / report; process files go to 工作记录", () => {
  assert.equal(resultKind("workspace/artifacts/bom/bom.rev1.json", "deliverable"), "final");
  assert.equal(resultKind("workspace/artifacts/report/lca_report.rev2.md"), "final");
  assert.equal(resultKind("workspace/artifacts/report/report.md", "deliverable"), "final");
  assert.equal(resultKind("workspace/artifacts/mapping/mapping.json", "deliverable"), "final");
  assert.equal(resultKind("workspace/artifacts/mapping/LCI/flows/x.json"), "final");
  assert.equal(resultKind("workspace/artifacts/LCI/processes/a.json"), "final");
  assert.equal(resultKind("workspace/artifacts/calculation-plan.json", "deliverable"), "work");
  assert.equal(resultKind("workspace/artifacts/process-mapping.json"), "work");
  assert.equal(resultKind("workspace/runs/lca-bom/status.json"), "work");
  assert.equal(resultKind("workspace/runs/lca-bom/status.json", "intermediate"), "work");
  assert.equal(resultKind("workspace/runs/_run/work-record.md"), "work");
  assert.equal(resultKind("workspace/runs/_run/events.jsonl"), "work");
});

test("reviewer verdict pass/fail have labels", async () => {
  const { VERDICT_LABEL } = await import("./result-kind.ts");
  assert.equal(VERDICT_LABEL.pass, "通过");
  assert.equal(VERDICT_LABEL.fail, "退回");
});
