import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { parseListenEndpoint, removeEndpointRecord } from "./endpoint.js";

test("parseListenEndpoint accepts a unix path and loopback tcp", () => {
  assert.deepEqual(parseListenEndpoint("/tmp/rt.sock"), {
    kind: "unix",
    path: "/tmp/rt.sock",
    raw: "/tmp/rt.sock",
  });
  assert.equal(parseListenEndpoint("tcp://127.0.0.1:39123").raw, "tcp://127.0.0.1:39123");
});

test("parseListenEndpoint rejects non-loopback hosts", () => {
  assert.throws(() => parseListenEndpoint("tcp://0.0.0.0:1"), /127\.0\.0\.1/);
  assert.throws(() => parseListenEndpoint("tcp://localhost:1"), /127\.0\.0\.1/);
  assert.throws(() => parseListenEndpoint("tcp://127.0.0.1:0"), /端口无效/);
});

test("removeEndpointRecord deletes only a matching line", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pirt-ep-"));
  fs.writeFileSync(path.join(dir, "pyproject.toml"), "");
  const file = path.join(dir, ".local", "run", "pi-runtime.endpoint");
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, "tcp://127.0.0.1:9\n");
  removeEndpointRecord("tcp://127.0.0.1:8", dir);
  assert.equal(fs.existsSync(file), true);
  removeEndpointRecord("tcp://127.0.0.1:9", dir);
  assert.equal(fs.existsSync(file), false);
  fs.rmSync(dir, { recursive: true, force: true });
});
