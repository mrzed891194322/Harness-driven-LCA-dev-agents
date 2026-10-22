import assert from "node:assert/strict";
import test from "node:test";
import { itemsToActivity, itemsToLog, lastNodeFromItems, nodeLabel, type RunItem } from "./run-items.ts";

const ts = "2026-10-23T09:15:02+0800";
const base = { ts, node: "lca-bom", rev: 2, redo: 1, agent: "executor", attempt: 1, model: "p/m-1" };
const items: RunItem[] = [
  { seq: 1, ts, kind: "note", text: "开始阶段 lca-bom（重做 1）" },
  { seq: 2, kind: "assistant_text", text: "读取计划", ...base },
  { seq: 3, kind: "tool_call", tool: "read", tool_call_id: "c1", summary: "plan/main_plan.md", ...base },
  { seq: 4, kind: "tool_result", tool: "read", tool_call_id: "c1", is_error: true, summary: "not found", ...base },
  { seq: 5, kind: "turn_end", ...base },
];

test("nodeLabel marks redo visits", () => {
  assert.equal(nodeLabel("lca-bom"), "lca-bom");
  assert.equal(nodeLabel("lca-bom", 2), "lca-bom（重做 2）");
});

test("itemsToLog keeps the progress tag format", () => {
  const log = itemsToLog(items);
  assert.match(log, /^\[orchestrator-09:15:02\] 开始阶段 lca-bom（重做 1）$/m);
  assert.match(log, /^\[lca-bom（重做 1）\(executor#1\)-m_1-09:15:02\]\n读取计划$/m);
  assert.match(log, /→ read plan\/main_plan\.md$/m);
  assert.match(log, /✗ read: not found$/m);
});

test("itemsToActivity and last node", () => {
  const act = itemsToActivity(items);
  assert.deepEqual(act.map((a) => a.kind), ["tool_call", "tool_result", "turn_end"]);
  assert.equal(act[0].node, "lca-bom（重做 1）");
  assert.equal(lastNodeFromItems("", items), "lca-bom（重做 1）");
});
