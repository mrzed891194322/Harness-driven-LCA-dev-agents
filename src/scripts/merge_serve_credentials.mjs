#!/usr/bin/env node
// Merge main-repo credentials into a serve (or other) worktree credentials dir.
//
// Rule: never wipe provider keys the target already has. Panel BYOK writes into
// the serve worktree; a blind `cp -r` from the main repo used to overwrite
// pi-auth.json and drop providers (e.g. google) that only lived in serve.
//
//   node src/scripts/merge_serve_credentials.mjs
//   node src/scripts/merge_serve_credentials.mjs --source <dir> --target <dir>
//
// Does not print any secret values — only provider names and file actions.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_SERVE_REL = path.join(
  ".local",
  "wt",
  "serve",
  "202606-harness-agent-LCA",
);

export function parseArgs(argv) {
  const out = { source: null, target: null, help: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") out.help = true;
    else if (a === "--source" || a === "-s") out.source = argv[++i];
    else if (a === "--target" || a === "-t") out.target = argv[++i];
    else throw new Error(`unknown argument: ${a}`);
  }
  return out;
}

function repoRootFromHere() {
  // src/scripts/merge_serve_credentials.mjs → repo root
  return path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, data) {
  const mode = 0o600;
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`, { mode });
  try {
    fs.chmodSync(file, mode);
  } catch {
    /* ignore on platforms without chmod */
  }
}

/** Merge pi-auth.json: keep every target provider; add providers only present in source. */
export function mergePiAuth(sourceAuth, targetAuth) {
  const src = sourceAuth && typeof sourceAuth === "object" ? sourceAuth : {};
  const dst = targetAuth && typeof targetAuth === "object" ? { ...targetAuth } : {};
  const added = [];
  for (const [provider, entry] of Object.entries(src)) {
    if (Object.prototype.hasOwnProperty.call(dst, provider)) continue;
    dst[provider] = entry;
    added.push(provider);
  }
  return { merged: dst, added, kept: Object.keys(dst).filter((k) => !(k in src) || true) };
}

function copyFileIfMissing(srcFile, dstFile, label, summary) {
  if (fs.existsSync(dstFile)) {
    summary.kept.push(label);
    return;
  }
  ensureDir(path.dirname(dstFile));
  fs.copyFileSync(srcFile, dstFile);
  summary.copied.push(label);
}

function copyDirIfMissing(srcDir, dstDir, label, summary) {
  if (fs.existsSync(dstDir)) {
    summary.kept.push(label);
    return;
  }
  fs.cpSync(srcDir, dstDir, { recursive: true });
  summary.copied.push(label);
}

/**
 * Merge credentials from sourceDir into targetDir.
 * Returns a summary with provider/file names only (no secret values).
 */
export function mergeCredentials(sourceDir, targetDir) {
  if (!fs.existsSync(sourceDir)) {
    throw new Error(`source credentials dir missing: ${sourceDir}`);
  }
  ensureDir(targetDir);

  const summary = {
    source: sourceDir,
    target: targetDir,
    piAuthAdded: [],
    piAuthProviders: [],
    copied: [],
    kept: [],
  };

  const srcAuthPath = path.join(sourceDir, "pi-auth.json");
  const dstAuthPath = path.join(targetDir, "pi-auth.json");
  if (fs.existsSync(srcAuthPath) || fs.existsSync(dstAuthPath)) {
    const srcAuth = fs.existsSync(srcAuthPath) ? readJson(srcAuthPath) : {};
    const dstAuth = fs.existsSync(dstAuthPath) ? readJson(dstAuthPath) : {};
    const { merged, added } = mergePiAuth(srcAuth, dstAuth);
    writeJson(dstAuthPath, merged);
    summary.piAuthAdded = added;
    summary.piAuthProviders = Object.keys(merged).sort();
  }

  // Top-level JSON markers (anthropic.json, google.json, …) and pi-models.json:
  // keep target copy if present; copy from source only when missing. Never delete
  // target-only markers.
  const names = new Set();
  for (const ent of fs.readdirSync(sourceDir, { withFileTypes: true })) {
    if (ent.isFile() && ent.name.endsWith(".json") && ent.name !== "pi-auth.json") {
      names.add(ent.name);
    }
  }
  for (const ent of fs.readdirSync(targetDir, { withFileTypes: true })) {
    if (ent.isFile() && ent.name.endsWith(".json") && ent.name !== "pi-auth.json") {
      names.add(ent.name);
    }
  }
  for (const name of [...names].sort()) {
    const srcFile = path.join(sourceDir, name);
    const dstFile = path.join(targetDir, name);
    if (fs.existsSync(dstFile)) {
      summary.kept.push(name);
      continue;
    }
    if (fs.existsSync(srcFile)) {
      copyFileIfMissing(srcFile, dstFile, name, summary);
    }
  }

  const srcAgent = path.join(sourceDir, "pi-agent");
  const dstAgent = path.join(targetDir, "pi-agent");
  if (fs.existsSync(srcAgent) && fs.statSync(srcAgent).isDirectory()) {
    copyDirIfMissing(srcAgent, dstAgent, "pi-agent/", summary);
  } else if (fs.existsSync(dstAgent)) {
    summary.kept.push("pi-agent/");
  }

  return summary;
}

function printSummary(summary) {
  // Names only — never dump key material.
  console.log(`merge_serve_credentials: ${summary.source} → ${summary.target}`);
  console.log(`  pi-auth providers: ${summary.piAuthProviders.join(", ") || "(none)"}`);
  if (summary.piAuthAdded.length) {
    console.log(`  pi-auth added from source: ${summary.piAuthAdded.join(", ")}`);
  } else {
    console.log("  pi-auth: no providers added (target kept)");
  }
  if (summary.copied.length) console.log(`  copied (missing in target): ${summary.copied.join(", ")}`);
  if (summary.kept.length) console.log(`  kept (already in target): ${summary.kept.join(", ")}`);
}

function usage() {
  console.log(`Usage: node src/scripts/merge_serve_credentials.mjs [--source DIR] [--target DIR]

Merge main-repo .local/credentials into a serve worktree credentials dir.
Target providers in pi-auth.json and existing marker files are preserved.
Defaults:
  --source  <repo>/.local/credentials
  --target  <repo>/.local/wt/serve/202606-harness-agent-LCA/.local/credentials`);
}

function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (args.help) {
    usage();
    return 0;
  }
  const root = repoRootFromHere();
  const source = path.resolve(args.source ?? path.join(root, ".local", "credentials"));
  const target = path.resolve(
    args.target ?? path.join(root, DEFAULT_SERVE_REL, ".local", "credentials"),
  );
  const summary = mergeCredentials(source, target);
  printSummary(summary);
  return 0;
}

const isMain =
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  try {
    process.exitCode = main();
  } catch (err) {
    console.error(`merge_serve_credentials failed: ${err?.message ?? err}`);
    process.exitCode = 1;
  }
}
