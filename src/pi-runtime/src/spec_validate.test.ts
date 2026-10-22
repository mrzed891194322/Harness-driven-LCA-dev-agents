import assert from "node:assert/strict";
import test from "node:test";
import { checkedLaunchSpec, launchSpecErrors } from "./spec_validate.js";

const spec = {
  schema_version: 2,
  run_id: "r1",
  node: "lca-bom",
  rev: 1,
  agent: "executor",
  attempt: 1,
  session_key: "v5:r1:lca-bom@rev1.executor",
  model_profile: { profile_id: "p/m", provider: "p", model_id: "m" },
  system_sections: [{ id: "v5_system", content: "S", source_hash: "h" }],
  turn_context: { engine: "v5" },
  knowledge_bindings: [],
  resource_bindings: { project_root: "/p", credentials_dir: "/c" },
  mcp_bindings: { submit: { command: "python", args: ["m.py"], env: { A: "1" }, exposure: "direct" } },
  permission_policy: { allowed_tools: ["read"], allowed_read_globs: [], allowed_write_globs: [], deny_shell: true },
  session_storage: { agent_dir: "/a", session_file: "/a/s.jsonl" },
};

test("a v2 launch spec passes", () => {
  assert.deepEqual(launchSpecErrors(spec), []);
  assert.equal(checkedLaunchSpec(spec).node, "lca-bom");
});

test("old or malformed specs are rejected", () => {
  assert.match(launchSpecErrors({ ...spec, schema_version: 1 }).join(), /schema_version: must be 2/);
  assert.match(launchSpecErrors({ ...spec, stage_id: "x" }).join(), /stage_id: unknown field/);
  const { node: _node, ...noNode } = spec;
  assert.match(launchSpecErrors(noNode).join(), /node: required/);
  const badMcp = { ...spec, mcp_bindings: { submit: { exposure: "loud" } } };
  assert.match(launchSpecErrors(badMcp).join(), /exposure: must be one of/);
  assert.throws(() => checkedLaunchSpec({ ...spec, rev: "1" }), /rev: must be integer/);
});
