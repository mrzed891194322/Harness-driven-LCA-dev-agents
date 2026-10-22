import assert from "node:assert/strict";
import test from "node:test";
import { isHandoffTool } from "./activity.js";

test("the v5 submit tool is the handoff", () => {
  assert.ok(isHandoffTool("submit"));
  assert.ok(isHandoffTool("mcp__submit__submit"));
  assert.ok(!isHandoffTool("submit_handoff"));
  assert.ok(!isHandoffTool("resubmit_draft"));
});
