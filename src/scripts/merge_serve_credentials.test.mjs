import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { mergeCredentials, mergePiAuth } from "./merge_serve_credentials.mjs";

test("mergePiAuth keeps target providers and only adds missing ones", () => {
  const source = {
    openai: { type: "api_key", key: "SRC_OPENAI" },
    deepseek: { type: "api_key", key: "SRC_DEEPSEEK" },
  };
  const target = {
    openai: { type: "api_key", key: "DST_OPENAI" },
    google: { type: "api_key", key: "DST_GOOGLE" },
  };
  const { merged, added } = mergePiAuth(source, target);
  assert.deepEqual(added.sort(), ["deepseek"]);
  assert.equal(merged.openai.key, "DST_OPENAI");
  assert.equal(merged.google.key, "DST_GOOGLE");
  assert.equal(merged.deepseek.key, "SRC_DEEPSEEK");
});

test("mergeCredentials preserves target-only markers and pi-auth providers", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "merge-cred-"));
  const source = path.join(root, "source");
  const target = path.join(root, "target");
  fs.mkdirSync(source);
  fs.mkdirSync(target);

  fs.writeFileSync(
    path.join(source, "pi-auth.json"),
    JSON.stringify({
      openai: { type: "api_key", key: "SRC_OPENAI" },
      anthropic: { type: "api_key", key: "SRC_ANTHROPIC" },
    }),
  );
  fs.writeFileSync(
    path.join(target, "pi-auth.json"),
    JSON.stringify({
      openai: { type: "api_key", key: "DST_OPENAI" },
      google: { type: "api_key", key: "DST_GOOGLE" },
    }),
  );

  fs.writeFileSync(
    path.join(source, "openai.json"),
    JSON.stringify({ provider: "openai", api_key_set: true }),
  );
  fs.writeFileSync(
    path.join(source, "anthropic.json"),
    JSON.stringify({ provider: "anthropic", api_key_set: true }),
  );
  fs.writeFileSync(
    path.join(source, "pi-models.json"),
    JSON.stringify({ models: ["src"] }),
  );
  // Target already has openai marker + google-only marker; pi-models missing.
  fs.writeFileSync(
    path.join(target, "openai.json"),
    JSON.stringify({ provider: "openai", api_key_set: true, note: "dst" }),
  );
  fs.writeFileSync(
    path.join(target, "google.json"),
    JSON.stringify({ provider: "google", api_key_set: true }),
  );

  fs.mkdirSync(path.join(source, "pi-agent"));
  fs.writeFileSync(path.join(source, "pi-agent", "settings.json"), '{"src":true}');
  fs.mkdirSync(path.join(target, "pi-agent"));
  fs.writeFileSync(path.join(target, "pi-agent", "settings.json"), '{"dst":true}');

  const summary = mergeCredentials(source, target);
  const auth = JSON.parse(fs.readFileSync(path.join(target, "pi-auth.json"), "utf8"));
  assert.equal(auth.openai.key, "DST_OPENAI");
  assert.equal(auth.google.key, "DST_GOOGLE");
  assert.equal(auth.anthropic.key, "SRC_ANTHROPIC");
  assert.deepEqual(summary.piAuthAdded.sort(), ["anthropic"]);

  const openaiMarker = JSON.parse(fs.readFileSync(path.join(target, "openai.json"), "utf8"));
  assert.equal(openaiMarker.note, "dst");
  assert.ok(fs.existsSync(path.join(target, "google.json")));
  assert.ok(fs.existsSync(path.join(target, "anthropic.json")));
  const models = JSON.parse(fs.readFileSync(path.join(target, "pi-models.json"), "utf8"));
  assert.deepEqual(models, { models: ["src"] });

  const agent = JSON.parse(fs.readFileSync(path.join(target, "pi-agent", "settings.json"), "utf8"));
  assert.deepEqual(agent, { dst: true });

  fs.rmSync(root, { recursive: true, force: true });
});

test("mergeCredentials copies pi-agent only when target lacks it", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "merge-cred-agent-"));
  const source = path.join(root, "source");
  const target = path.join(root, "target");
  fs.mkdirSync(source);
  fs.mkdirSync(target);
  fs.writeFileSync(path.join(source, "pi-auth.json"), "{}");
  fs.mkdirSync(path.join(source, "pi-agent"));
  fs.writeFileSync(path.join(source, "pi-agent", "settings.json"), '{"src":1}');

  mergeCredentials(source, target);
  assert.ok(fs.existsSync(path.join(target, "pi-agent", "settings.json")));
  const agent = JSON.parse(fs.readFileSync(path.join(target, "pi-agent", "settings.json"), "utf8"));
  assert.deepEqual(agent, { src: 1 });
  fs.rmSync(root, { recursive: true, force: true });
});
