import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { PathGuard, type GuardRecord } from "./path_guard.js";

function setup() {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pguard-")));
  fs.mkdirSync(path.join(root, "workspace", "runs"), { recursive: true });
  fs.mkdirSync(path.join(root, "harness", "knowledge"), { recursive: true });
  fs.mkdirSync(path.join(root, "harness", "prompts"), { recursive: true });
  fs.mkdirSync(path.join(root, "docs"), { recursive: true });
  fs.writeFileSync(path.join(root, "workspace", "a.txt"), "a");
  fs.writeFileSync(path.join(root, "harness", "knowledge", "k.md"), "k");
  fs.mkdirSync(path.join(root, "docs", "ops"), { recursive: true });
  fs.writeFileSync(path.join(root, "docs", "ops", "ISSUES.md"), "secret");
  fs.symlinkSync(path.join(root, "docs"), path.join(root, "workspace", "escape"));
  const records: GuardRecord[] = [];
  const logFile = path.join(root, ".local", "guard.jsonl");
  const guard = new PathGuard({
    sessionKey: "s",
    cwd: root,
    readGlobs: [`${root}/workspace/**`, `${root}/harness/knowledge/**`],
    writeGlobs: [`${root}/workspace/**`],
    logFile,
    notify: (r) => records.push(r),
  });
  return { root, guard, records, logFile };
}

test("read inside workspace is allowed", () => {
  const { guard } = setup();
  assert.equal(guard.onToolCall("read", { path: "workspace/a.txt" }), undefined);
  assert.equal(guard.onToolCall("write", { path: "workspace/runs/new/out.json" }), undefined);
});

test("read under harness/knowledge is allowed", () => {
  const { guard } = setup();
  assert.equal(guard.onToolCall("read", { path: "harness/knowledge/k.md" }), undefined);
  assert.equal(guard.onToolCall("grep", { pattern: "x", path: "harness/knowledge" }), undefined);
});

test("docs/ and other harness content are denied and logged", () => {
  const { guard, records, logFile, root } = setup();
  const res = guard.onToolCall("read", { path: "docs/ops/ISSUES.md" });
  assert.equal(res?.block, true);
  assert.match(res!.reason, /权限拒绝/);
  assert.equal(guard.onToolCall("ls", { path: "harness/prompts" })?.block, true);
  assert.equal(records[0].action, "denied");
  assert.equal(records[0].resolved_path, path.join(root, "docs", "ops", "ISSUES.md"));
  assert.ok(fs.readFileSync(logFile, "utf8").includes("docs/ops/ISSUES.md"));
});

test("../ escape is denied", () => {
  const { guard } = setup();
  assert.equal(guard.onToolCall("read", { path: "workspace/../docs/ops/ISSUES.md" })?.block, true);
  assert.equal(guard.onToolCall("find", { pattern: "*", path: "workspace/.." })?.block, true);
});

test("symlink escape is denied", () => {
  const { guard } = setup();
  assert.equal(guard.onToolCall("read", { path: "workspace/escape/ISSUES.md" })?.block, true);
  assert.equal(guard.onToolCall("write", { path: "workspace/escape/new.md" })?.block, true);
});

test("write outside workspace is denied (even in readable knowledge)", () => {
  const { guard } = setup();
  assert.equal(guard.onToolCall("write", { path: "harness/knowledge/k.md" })?.block, true);
  assert.equal(guard.onToolCall("edit", { path: "/tmp/x.txt", edits: [] })?.block, true);
});

test("grep/find/ls without path are pointed at the workspace", () => {
  const { guard, root } = setup();
  const input: Record<string, unknown> = { pattern: "x" };
  assert.equal(guard.onToolCall("grep", input), undefined);
  assert.equal(input.path, path.join(root, "workspace"));
});

test("bash is logged, not blocked; out-of-scope paths flagged", () => {
  const { guard, records } = setup();
  assert.equal(guard.onToolCall("bash", { command: "cat docs/ops/ISSUES.md && ls workspace/" }), undefined);
  const rec = records.at(-1)!;
  assert.equal(rec.action, "bash_command");
  assert.deepEqual(rec.out_of_scope?.map((f) => f.requested), ["docs/ops/ISSUES.md"]);
});

test("empty scopes deny everything (fail closed)", () => {
  const g = new PathGuard({ sessionKey: "s", cwd: "/tmp", readGlobs: [], writeGlobs: [] });
  assert.equal(g.onToolCall("read", { path: "/etc/hostname" })?.block, true);
  assert.equal(g.onToolCall("write", { path: "/tmp/x" })?.block, true);
  assert.equal(g.onToolCall("ls", {})?.block, true);
});

test("spec_mcp-owned deliverable paths are write-denied even inside the write scope", () => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "pguard-deny-")));
  fs.mkdirSync(path.join(root, "workspace", "artifacts"), { recursive: true });
  const official = path.join(root, "workspace", "artifacts", "process-mapping.json");
  fs.writeFileSync(official, "{}");
  const records: GuardRecord[] = [];
  const guard = new PathGuard({
    sessionKey: "s",
    cwd: root,
    readGlobs: [`${root}/workspace/**`],
    writeGlobs: [`${root}/workspace/**`],
    deniedWriteGlobs: [official],
    notify: (r) => records.push(r),
  });
  for (const tool of ["write", "edit"]) {
    const res = guard.onToolCall(tool, { path: "workspace/artifacts/process-mapping.json" });
    assert.equal(res?.block, true, tool);
    assert.match(res!.reason, /spec_mcp/);
  }
  // ../ tricks resolve to the same file and are still denied
  assert.equal(
    guard.onToolCall("write", { path: "workspace/drafts/../artifacts/process-mapping.json" })?.block,
    true,
  );
  // drafts elsewhere stay writable, and the official file stays readable
  assert.equal(guard.onToolCall("write", { path: "workspace/drafts/process-mapping.json" }), undefined);
  assert.equal(guard.onToolCall("read", { path: "workspace/artifacts/process-mapping.json" }), undefined);
  assert.equal(records.filter((r) => r.action === "denied").length, 3);
});

test("official deliverable paths are write-denied even inside workspace (spec_mcp only)", () => {
  const { root } = setup();
  const records: GuardRecord[] = [];
  const guard = new PathGuard({
    sessionKey: "s",
    cwd: root,
    readGlobs: [`${root}/workspace/**`],
    writeGlobs: [`${root}/workspace/**`],
    deniedWriteGlobs: [`${root}/workspace/artifacts/process-mapping.json`],
    logFile: path.join(root, ".local", "guard2.jsonl"),
    notify: (r) => records.push(r),
  });
  for (const tool of ["write", "edit"]) {
    const res = guard.onToolCall(tool, { path: "workspace/artifacts/process-mapping.json" });
    assert.ok(res && res.block, `${tool} to official path must be blocked`);
    assert.match(String(res.reason), /spec_mcp/);
  }
  assert.equal(guard.onToolCall("read", { path: "workspace/artifacts/process-mapping.json" }), undefined);
  assert.equal(guard.onToolCall("write", { path: "workspace/tmp/process-mapping.json" }), undefined);
  assert.equal(records.length, 2);
});

test("stage deny_write glob workspace/artifacts/** blocks the whole subtree", () => {
  const { root } = setup();
  const guard = new PathGuard({
    sessionKey: "s",
    cwd: root,
    readGlobs: [`${root}/workspace/**`],
    writeGlobs: [`${root}/workspace/**`],
    deniedWriteGlobs: [`${root}/workspace/artifacts/**`],
    notify: () => {},
  });
  assert.equal(guard.onToolCall("write", { path: "workspace/artifacts/LCI/processes/p.json" })?.block, true);
  assert.equal(guard.onToolCall("write", { path: "workspace/artifacts/LCI/human_readable_mapping.md" })?.block, true);
  assert.equal(guard.onToolCall("write", { path: "workspace/runs/03-dataset-mapping/executor-1/LCI/p.json" }), undefined);
});

test("write to the write-root path itself is denied (must be a child path)", () => {
  const { guard, root } = setup();
  const res = guard.onToolCall("write", { path: "workspace", content: "notes" });
  assert.equal(res?.block, true);
  assert.match(res!.reason, /不能把写入根目录本身写成文件/);
  assert.equal(guard.onToolCall("write", { path: "workspace/runs/notes.md", content: "ok" }), undefined);
  // exact write-root file replace after mkdir root exists
  const rev = path.join(root, "workspace", "runs", "n", "reviewer");
  fs.mkdirSync(rev, { recursive: true });
  const g2 = new PathGuard({
    sessionKey: "s",
    cwd: root,
    readGlobs: [`${root}/workspace/**`],
    writeGlobs: [`${rev}/**`],
  });
  assert.equal(g2.onToolCall("write", { path: rev, content: "notes" })?.block, true);
  assert.equal(g2.onToolCall("write", { path: path.join(rev, "notes.md"), content: "ok" }), undefined);
});
