import { test } from "node:test";
import assert from "node:assert/strict";
import {
  coerceStringifiedArrayArgs,
  installArgCoerceOnSession,
  schemaAllowsArray,
  tryParseJsonArray,
} from "./arg_coerce.js";

const submitParams = {
  type: "object",
  properties: {
    status: { type: "string" },
    summary: { anyOf: [{ type: "string" }, { type: "null" }] },
    artifacts: {
      anyOf: [{ type: "array", items: { type: "string" } }, { type: "null" }],
    },
  },
};

const writeParams = {
  type: "object",
  properties: {
    path: { type: "string" },
    content: { type: "string" },
  },
};

const reviewerParams = {
  type: "object",
  properties: {
    verdict: { type: "string" },
    issues: {
      anyOf: [
        {
          type: "array",
          items: {
            type: "object",
            properties: {
              where: { type: "string" },
              problem: { type: "string" },
              expected: { type: "string" },
            },
          },
        },
        { type: "null" },
      ],
    },
  },
};

test("schemaAllowsArray detects array and anyOf-array", () => {
  assert.equal(schemaAllowsArray({ type: "array" }), true);
  assert.equal(schemaAllowsArray({ anyOf: [{ type: "array" }, { type: "null" }] }), true);
  assert.equal(schemaAllowsArray({ type: "string" }), false);
  assert.equal(schemaAllowsArray({ anyOf: [{ type: "string" }, { type: "null" }] }), false);
});

test("tryParseJsonArray only accepts JSON arrays", () => {
  assert.deepEqual(tryParseJsonArray('["a","b"]'), ["a", "b"]);
  assert.deepEqual(tryParseJsonArray(["a"]), ["a"]);
  assert.equal(tryParseJsonArray('{"a":1}'), '{"a":1}');
  assert.equal(tryParseJsonArray("not-json"), "not-json");
  assert.equal(tryParseJsonArray('"just-a-string"'), '"just-a-string"');
});

test("coerce stringified artifacts to array; leave already-array; leave bad string", () => {
  const stringified = {
    status: "done",
    summary: "ok",
    artifacts: '["workspace/artifacts/bom/claims.json"]',
  };
  coerceStringifiedArrayArgs(stringified, submitParams);
  assert.deepEqual(stringified.artifacts, ["workspace/artifacts/bom/claims.json"]);

  const already = { status: "done", artifacts: ["/a"] };
  coerceStringifiedArrayArgs(already, submitParams);
  assert.deepEqual(already.artifacts, ["/a"]);

  const bad = { status: "done", artifacts: "[not-json" };
  coerceStringifiedArrayArgs(bad, submitParams);
  assert.equal(bad.artifacts, "[not-json");
});

test("write/edit content stays string even if it looks like a JSON array", () => {
  const args = { path: "a.txt", content: '["do-not-parse"]' };
  coerceStringifiedArrayArgs(args, writeParams);
  assert.equal(args.content, '["do-not-parse"]');
});

test("reviewer issues stringified array is coerced", () => {
  const args = {
    verdict: "reject",
    issues: '[{"where":"a","problem":"b","expected":"c"}]',
  };
  coerceStringifiedArrayArgs(args, reviewerParams);
  assert.deepEqual(args.issues, [{ where: "a", problem: "b", expected: "c" }]);
});

test("installArgCoerceOnSession wires prepareArguments before validation shape", () => {
  const def: {
    name: string;
    parameters: typeof submitParams;
    prepareArguments?: (args: unknown) => unknown;
  } = {
    name: "mcp__submit__submit",
    parameters: submitParams,
  };
  const live: {
    name: string;
    parameters: typeof submitParams;
    prepareArguments?: (args: unknown) => unknown;
  } = {
    name: "mcp__submit__submit",
    parameters: submitParams,
  };
  const session = {
    getAllTools: () => [{ name: def.name }],
    getToolDefinition: (name: string) => (name === def.name ? def : undefined),
    _toolRegistry: new Map([[live.name, live]]),
  };
  assert.equal(installArgCoerceOnSession(session), 2);
  assert.equal(installArgCoerceOnSession(session), 0); // idempotent

  const raw = {
    status: "done",
    summary: "x",
    artifacts: '["/tmp/claims.json"]',
  };
  const prepared = def.prepareArguments!(raw) as typeof raw;
  assert.deepEqual(prepared.artifacts, ["/tmp/claims.json"]);
  const preparedLive = live.prepareArguments!(structuredClone(raw)) as typeof raw;
  assert.deepEqual(preparedLive.artifacts, ["/tmp/claims.json"]);
});
