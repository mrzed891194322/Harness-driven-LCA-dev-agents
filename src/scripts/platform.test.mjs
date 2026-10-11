import assert from "node:assert/strict";
import test from "node:test";
import { parseListenEndpoint } from "./endpoint.mjs";
import {
  findGitBash,
  isWindowsSystemBash,
  parseWin32ProcessList,
  prependPath,
} from "./platform.mjs";

test("parseListenEndpoint matches the runtime rules", () => {
  assert.equal(parseListenEndpoint("tcp://127.0.0.1:9").kind, "tcp");
  assert.equal(parseListenEndpoint("  /tmp/rt.sock ").kind, "unix");
  assert.throws(() => parseListenEndpoint("tcp://10.0.0.1:9"), /127\.0\.0\.1/);
});

test("findGitBash ignores System32 and uses known Git locations", () => {
  assert.equal(isWindowsSystemBash("C:\\Windows\\System32\\bash.exe"), true);
  assert.equal(isWindowsSystemBash("C:\\Program Files\\Git\\bin\\bash.exe"), false);
  const env = {
    ProgramFiles: "C:\\Program Files",
    "ProgramFiles(x86)": "C:\\Program Files (x86)",
    LOCALAPPDATA: "C:\\Users\\me\\AppData\\Local",
  };
  const present = new Set(["C:\\Users\\me\\AppData\\Local\\Programs\\Git\\bin\\bash.exe"]);
  const found = findGitBash(env, (file) => present.has(file));
  assert.equal(found.path, "C:\\Users\\me\\AppData\\Local\\Programs\\Git\\bin\\bash.exe");
  const rejected = findGitBash(
    { ...env, PI_BASH: "C:\\Windows\\System32\\bash.exe" },
    () => true,
  );
  assert.match(rejected.error, /请检查是否将Git for Windows安装在默认路径，或在PATH中加入bash.exe/);
  assert.match(rejected.error, /add bash.exe to PATH/);
  const missing = findGitBash(env, () => false);
  assert.match(missing.error, /请检查是否将Git for Windows安装在默认路径，或在PATH中加入bash.exe/);
  assert.match(missing.error, /Check whether Git for Windows is installed in the default location/);

  const onPath = "D:\\Tools\\Git\\bin\\bash.exe";
  const fromPath = findGitBash(
    { ...env, Path: "C:\\Windows\\System32;D:\\Tools\\Git\\bin" },
    (file) => file === onPath,
    ";",
  );
  assert.equal(fromPath.path, onPath);
});

test("prependPath puts the Git bin directory first", () => {
  const env = { Path: "C:\\Windows\\System32;C:\\Program Files\\Git\\bin" };
  prependPath(env, "C:\\Program Files\\Git\\bin", ";");
  assert.equal(env.Path, "C:\\Program Files\\Git\\bin;C:\\Windows\\System32");
});

test("parseWin32ProcessList keeps this checkout's runtime", () => {
  const root = "C:\\src\\harness";
  const stdout = JSON.stringify([
    {
      ProcessId: 4,
      CommandLine: "node C:\\src\\harness\\src\\pi-runtime\\dist\\main.js --listen tcp://127.0.0.1:1",
    },
    { ProcessId: 5, CommandLine: "node D:\\other\\src\\pi-runtime\\dist\\main.js" },
    { ProcessId: 6, CommandLine: null },
  ]);
  assert.deepEqual(parseWin32ProcessList(stdout, root, 0), [
    {
      pid: 4,
      kind: "pi-runtime",
      args: "node C:\\src\\harness\\src\\pi-runtime\\dist\\main.js --listen tcp://127.0.0.1:1",
    },
  ]);
});
