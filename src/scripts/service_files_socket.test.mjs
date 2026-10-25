import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import {
  UNIX_SOCK_PATH_MAX,
  defaultRuntimeSocketPath,
  isServeWorktree,
  mainRepoRoot,
  runtimeSocket,
} from "./service_files.mjs";

const MAIN = path.join("/home", "yuandu", "Programming", "202606-harness-agent-LCA");
const SERVE = path.join(MAIN, ".local", "wt", "serve", "202606-harness-agent-LCA");
const DEV_WT = path.join(MAIN, ".local", "wt", "202606-harness-agent-LCA");

test("mainRepoRoot strips .local/wt nested worktrees", () => {
  assert.equal(mainRepoRoot(MAIN), path.resolve(MAIN));
  assert.equal(mainRepoRoot(SERVE), path.resolve(MAIN));
  assert.equal(mainRepoRoot(DEV_WT), path.resolve(MAIN));
});

test("isServeWorktree detects serve checkout only", () => {
  assert.equal(isServeWorktree(SERVE), true);
  assert.equal(isServeWorktree(DEV_WT), false);
  assert.equal(isServeWorktree(MAIN), false);
});

test("defaultRuntimeSocketPath uses short main-repo socks for long worktrees", () => {
  const mainSock = defaultRuntimeSocketPath(MAIN);
  assert.equal(mainSock, path.join(path.resolve(MAIN), ".local", "run", "pi-runtime.sock"));
  assert.ok(Buffer.byteLength(mainSock, "utf8") < UNIX_SOCK_PATH_MAX);

  const serveSock = defaultRuntimeSocketPath(SERVE);
  assert.equal(serveSock, path.join(path.resolve(MAIN), ".local", "run", "pi-v5serve.sock"));
  assert.ok(Buffer.byteLength(serveSock, "utf8") < UNIX_SOCK_PATH_MAX);

  const nestedDefault = path.join(path.resolve(SERVE), ".local", "run", "pi-runtime.sock");
  assert.ok(Buffer.byteLength(nestedDefault, "utf8") >= UNIX_SOCK_PATH_MAX);

  const devSock = defaultRuntimeSocketPath(DEV_WT);
  assert.equal(devSock, path.join(path.resolve(MAIN), ".local", "run", "pi-runtime.sock"));
  assert.ok(Buffer.byteLength(devSock, "utf8") < UNIX_SOCK_PATH_MAX);
});

test("runtimeSocket respects PI_RUNTIME_SOCKET override", () => {
  const override = path.join(path.resolve(MAIN), ".local", "run", "custom.sock");
  const got = runtimeSocket({ PI_RUNTIME_SOCKET: override }, SERVE);
  assert.equal(got, path.resolve(override));
});

test("runtimeSocket falls back to short default when no override", () => {
  // Clear override; no endpoint file under this fake path → short default.
  const got = runtimeSocket({ PI_RUNTIME_SOCKET: "" }, SERVE);
  assert.equal(got, path.join(path.resolve(MAIN), ".local", "run", "pi-v5serve.sock"));
});
