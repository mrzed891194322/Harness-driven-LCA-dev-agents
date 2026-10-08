import assert from "node:assert/strict";
import test from "node:test";
import { emitResponse } from "./protocol.js";

test("protocol response shape", () => {
  const lines: string[] = [];
  const orig = process.stdout.write.bind(process.stdout);
  process.stdout.write = (chunk: string | Uint8Array) => {
    lines.push(String(chunk));
    return true;
  };
  emitResponse({ type: "res", id: "1", ok: true, result: { ok: true } });
  process.stdout.write = orig;
  const parsed = JSON.parse(lines[0].trim());
  assert.equal(parsed.type, "res");
  assert.equal(parsed.id, "1");
});
