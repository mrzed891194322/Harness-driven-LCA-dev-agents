import test from "node:test";
import assert from "node:assert/strict";
import { workflowForMode, type WorkflowCard } from "./workflow-cards.ts";

const wf = (id: string, revise: string | null = null): WorkflowCard => ({ id, plan_file: "x.md", start_rev: revise ? "next" : "zero", nodes: [], details: [] });

test("plan mode picks full-lca / the revise workflow", () => {
  const list = [wf("demo-single"), wf("full-lca"), wf("revise-lca", "full-lca")];
  assert.equal(workflowForMode(list, "new")?.id, "full-lca");
  assert.equal(workflowForMode(list, "revise")?.id, "revise-lca");
  assert.equal(workflowForMode([wf("demo-single")], "revise"), undefined);
});
