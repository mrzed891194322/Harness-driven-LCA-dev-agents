// Project-local package caches for the launcher (uv and npm).
//
// Sandboxed agents (Codex's workspace-write, this repo's DSH workspace-write,
// Cursor) can only write inside the checkout. uv's default cache (~/.cache/uv)
// and npm's (~/.npm) are read-only there, so `uv sync` / `npm install` die with
// "Read-only file system" before the control panel starts.
//
// Python already pins UV_CACHE_DIR to <repo>/.uv-cache itself
// (src/backend/core/agents/uv_env.py, ISSUES #16). The launcher has to do the
// same before it spawns uv, because .env is not merged into process.env.
import path from "node:path";

const UV_CACHE_REL = ".uv-cache";
const NPM_CACHE_REL = ".npm-cache";

function unquote(value) {
  return String(value ?? "")
    .trim()
    .replace(/^["']|["']$/g, "");
}

/** Keep a configured cache only when it stays inside the project. */
function resolveCacheDir(projectRoot, raw, fallbackRel) {
  const root = path.resolve(projectRoot);
  const value = unquote(raw);
  if (!value) return path.join(root, fallbackRel);
  // "~/.cache/uv" is the home directory, which the sandbox makes read-only.
  if (value === "~" || value.startsWith("~/") || value.startsWith("~\\")) {
    return path.join(root, fallbackRel);
  }
  const resolved = path.resolve(root, value);
  const rel = path.relative(root, resolved);
  const inside = rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
  return inside ? resolved : path.join(root, fallbackRel);
}

export function projectUvCacheDir(projectRoot, env = process.env) {
  return resolveCacheDir(projectRoot, env.UV_CACHE_DIR, UV_CACHE_REL);
}

export function projectNpmCacheDir(projectRoot, env = process.env) {
  return resolveCacheDir(projectRoot, env.npm_config_cache, NPM_CACHE_REL);
}

/** Pin both caches on `env`, so this process and every child inherit them. */
export function ensureProjectCaches(projectRoot, env = process.env) {
  const uv = projectUvCacheDir(projectRoot, env);
  const npm = projectNpmCacheDir(projectRoot, env);
  env.UV_CACHE_DIR = uv;
  env.npm_config_cache = npm;
  return { uv, npm };
}
