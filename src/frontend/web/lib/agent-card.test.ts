import test from "node:test";
import assert from "node:assert/strict";
import { modelLine } from "./agent-card.ts";

test("model cell shows the resolved model id and thinking level", () => {
  assert.equal(modelLine({ model: "opencode-go/deepseek-v4.1-flash", thinking: "high", model_source: "default" }),
    "opencode-go/deepseek-v4.1-flash（默认） · 思考 high");
  assert.equal(modelLine({ model: "x/y", thinking: "low", model_source: "agent" }), "x/y · 思考 low");
});
