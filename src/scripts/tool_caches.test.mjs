import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import {
  ensureProjectCaches,
  projectNpmCacheDir,
  projectUvCacheDir,
} from "./tool_caches.mjs";

const root = path.resolve("/repo");

test("unset caches fall back to the project", () => {
  assert.equal(projectUvCacheDir(root, {}), path.join(root, ".uv-cache"));
  assert.equal(projectNpmCacheDir(root, {}), path.join(root, ".npm-cache"));
});

test("relative and in-project caches are kept", () => {
  assert.equal(projectUvCacheDir(root, { UV_CACHE_DIR: ".uv-cache" }), path.join(root, ".uv-cache"));
  assert.equal(projectUvCacheDir(root, { UV_CACHE_DIR: '"cache/uv"' }), path.join(root, "cache/uv"));
  assert.equal(projectNpmCacheDir(root, { npm_config_cache: "cache/npm" }), path.join(root, "cache/npm"));
});

test("caches outside the project fall back, as the Python side does", () => {
  assert.equal(projectUvCacheDir(root, { UV_CACHE_DIR: "/tmp/cursor-sandbox-cache/uv" }), path.join(root, ".uv-cache"));
  assert.equal(projectUvCacheDir(root, { UV_CACHE_DIR: "~/.cache/uv" }), path.join(root, ".uv-cache"));
  assert.equal(projectNpmCacheDir(root, { npm_config_cache: "/home/u/.npm" }), path.join(root, ".npm-cache"));
});

test("ensureProjectCaches exports both caches to children", () => {
  const env = { UV_CACHE_DIR: "/tmp/read-only-cache", npm_config_cache: "/home/u/.npm" };
  const caches = ensureProjectCaches(root, env);
  assert.deepEqual(caches, {
    uv: path.join(root, ".uv-cache"),
    npm: path.join(root, ".npm-cache"),
  });
  assert.equal(env.UV_CACHE_DIR, caches.uv);
  assert.equal(env.npm_config_cache, caches.npm);
});
