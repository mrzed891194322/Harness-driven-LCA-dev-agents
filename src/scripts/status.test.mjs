import assert from "node:assert/strict";
import test from "node:test";
import {
  classifyPanel,
  formatPanelReport,
  mergeProcesses,
  panelPort,
} from "./status_lib.mjs";

const services = [
  { name: "backend", pid: 1 },
  { name: "pi-runtime", pid: 2 },
  { name: "web", pid: 3 },
];

test("ready only when backend, pi-runtime, and web are alive and health is ok", () => {
  assert.equal(classifyPanel(services, true), "ready");
  assert.equal(classifyPanel(services, false), "partial");
  assert.equal(classifyPanel([{ name: "pi-runtime", pid: 2 }], false), "partial");
  assert.equal(classifyPanel([], false), "stopped");
  assert.equal(classifyPanel([], true), "partial");
});

test("merge keeps pid-file entries and drops a duplicate stray pid", () => {
  const merged = mergeProcesses(
    [{ name: "pi-runtime", pid: 8 }],
    [
      { name: "pi-runtime", pid: 8 },
      { name: "mcp", pid: 9 },
      { name: "other", pid: 10 },
    ],
  );
  assert.deepEqual(merged, [
    { name: "pi-runtime", pid: 8 },
    { name: "mcp", pid: 9 },
  ]);
});

test("report is one machine-readable status plus addresses and pids", () => {
  const text = formatPanelReport({
    status: "partial",
    webPort: 3000,
    apiPort: 8800,
    endpoint: "tcp://127.0.0.1:9",
    healthOk: false,
    processes: [{ name: "pi-runtime", pid: 8 }],
  });
  assert.match(text, /^status=partial\n进程残缺\n/);
  assert.match(text, /web=http:\/\/127\.0\.0\.1:3000\n/);
  assert.match(text, /api=http:\/\/127\.0\.0\.1:8800\n/);
  assert.match(text, /endpoint=tcp:\/\/127\.0\.0\.1:9\n/);
  assert.match(text, /health=down\n/);
  assert.match(text, /pi-runtime=8\n$/);
});

test("panelPort strips nothing and rejects a bad value", () => {
  assert.equal(panelPort("3000", "1"), 3000);
  assert.equal(panelPort("", "8800"), 8800);
  assert.throws(() => panelPort("nope", "8800"), /invalid port: nope/);
});
