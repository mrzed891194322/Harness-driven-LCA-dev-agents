import test from "node:test";
import assert from "node:assert/strict";
import { workflowForMode, type V5Workflow } from "./v5-workflow.ts";

const wf = (id: string, revise_of: string | null = null): V5Workflow => ({ id, plan_file: "x.md", revise_of, nodes: [], details: [] });

test("plan mode picks full-lca / the revise workflow", () => {
  const list = [wf("demo-single"), wf("full-lca"), wf("revise-lca", "full-lca")];
  assert.equal(workflowForMode(list, "new")?.id, "full-lca");
  assert.equal(workflowForMode(list, "revise")?.id, "revise-lca");
  assert.equal(workflowForMode([wf("demo-single")], "revise"), undefined);
});
