import assert from "node:assert/strict";
import test from "node:test";
import { modelChoices } from "./model-options.ts";

const rows = [
  { id: "opencode-go/glm-5", label: "GLM 5", provider_name: "OpenCode Go" },
  { id: "openai/gpt-x", label: "GPT X" },
];

test("selected default is the current value", () => {
  const r = modelChoices(rows, "openai/gpt-x");
  assert.equal(r.value, "openai/gpt-x");
  assert.equal(r.choices.length, 2);
  assert.equal(r.choices[0].label, "OpenCode Go · GLM 5");
});

test("a saved default that is not listed stays visible", () => {
  const r = modelChoices(rows, "custom/m1");
  assert.deepEqual(r.choices[0], { value: "custom/m1", label: "custom/m1（当前）" });
});

test("no default yet shows a placeholder", () => {
  const r = modelChoices(rows, "");
  assert.equal(r.value, "");
  assert.equal(r.choices[0].value, "");
});
