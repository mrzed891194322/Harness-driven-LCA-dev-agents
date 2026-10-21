import { test } from "node:test";
import assert from "node:assert/strict";
import { MCP_NOT_READY, withMcpRetry } from "./session_host.js";

test("MCP not ready is retried once, other errors are not", async () => {
  let n = 0;
  const logs: string[] = [];
  const ok = await withMcpRetry(async () => {
    n += 1;
    if (n === 1) throw new Error(`${MCP_NOT_READY}：submit`);
    return "live";
  }, 2, (m) => logs.push(m));
  assert.equal(ok, "live");
  assert.equal(logs.length, 1);
  n = 0;
  await assert.rejects(withMcpRetry(async () => { n += 1; throw new Error(`${MCP_NOT_READY}：submit`); }), /MCP/);
  assert.equal(n, 2);
  n = 0;
  await assert.rejects(withMcpRetry(async () => { n += 1; throw new Error("模型不可用"); }), /模型不可用/);
  assert.equal(n, 1);
});
