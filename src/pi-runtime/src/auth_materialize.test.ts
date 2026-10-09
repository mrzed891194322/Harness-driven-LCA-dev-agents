import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  materializeAuthJson,
  materializeModelsJson,
  providerHasAuth,
  readPiAuthFile,
} from "./auth_materialize.js";

test("materializeAuthJson copies Pi auth.json shape from pi-auth.json", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pi-auth-"));
  const creds = path.join(root, "credentials");
  const agent = path.join(root, "agent");
  fs.mkdirSync(creds, { recursive: true });
  fs.writeFileSync(
    path.join(creds, "pi-auth.json"),
    JSON.stringify({
      anthropic: { type: "api_key", key: "sk-test" },
    }),
    "utf8",
  );
  const dest = materializeAuthJson(creds, agent);
  const auth = JSON.parse(fs.readFileSync(dest, "utf8"));
  assert.equal(auth.anthropic.type, "api_key");
  assert.equal(auth.anthropic.key, "sk-test");
});

test("materializeAuthJson preserves OAuth credentials", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pi-oauth-"));
  const creds = path.join(root, "credentials");
  const agent = path.join(root, "agent");
  fs.mkdirSync(creds, { recursive: true });
  fs.writeFileSync(
    path.join(creds, "pi-auth.json"),
    JSON.stringify({
      openai: {
        type: "oauth",
        access: "access-token",
        refresh: "refresh-token",
        expires: 9999999999999,
      },
    }),
    "utf8",
  );
  const dest = materializeAuthJson(creds, agent);
  const auth = JSON.parse(fs.readFileSync(dest, "utf8"));
  assert.equal(auth.openai.type, "oauth");
  assert.equal(auth.openai.access, "access-token");
  assert.equal(auth.openai.refresh, "refresh-token");
  assert.ok(providerHasAuth(auth, "openai"));
});

test("readPiAuthFile accepts legacy providers.apiKey wrapper", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pi-auth-legacy-"));
  const file = path.join(root, "pi-auth.json");
  fs.writeFileSync(
    file,
    JSON.stringify({
      providers: { openai: { apiKey: "sk-legacy" } },
    }),
    "utf8",
  );
  const auth = readPiAuthFile(file);
  assert.equal(auth.openai?.key, "sk-legacy");
  assert.equal(auth.openai?.type, "api_key");
});

test("materializeModelsJson writes custom endpoint only when api_type/base_url set", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pi-models-"));
  const agent = path.join(root, "agent");
  assert.equal(
    materializeModelsJson(
      { profile_id: "default", provider: "anthropic", model_id: "claude-sonnet-4-5" },
      agent,
    ),
    null,
  );
  const dest = materializeModelsJson(
    {
      profile_id: "local",
      provider: "ollama",
      model_id: "qwen2.5",
      api_type: "openai-completions",
      base_url: "http://localhost:11434/v1",
    },
    agent,
  );
  assert.ok(dest);
  const models = JSON.parse(fs.readFileSync(dest!, "utf8"));
  assert.equal(models.providers.ollama.baseUrl, "http://localhost:11434/v1");
  assert.equal(models.providers.ollama.api, "openai-completions");
  assert.equal(models.providers.ollama.models[0].id, "qwen2.5");
  assert.equal(models.providers.ollama.apiKey, "local");
});

test("materializeModelsJson merges pi-models.json baseUrl overrides", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pi-models-override-"));
  const creds = path.join(root, "credentials");
  const agent = path.join(root, "agent");
  fs.mkdirSync(creds, { recursive: true });
  fs.writeFileSync(
    path.join(creds, "pi-models.json"),
    JSON.stringify({
      providers: {
        anthropic: { baseUrl: "https://proxy.example/anthropic" },
      },
    }),
    "utf8",
  );
  const dest = materializeModelsJson(
    { profile_id: "default", provider: "anthropic", model_id: "claude-sonnet-4-5" },
    agent,
    creds,
  );
  assert.ok(dest);
  const models = JSON.parse(fs.readFileSync(dest!, "utf8"));
  assert.equal(models.providers.anthropic.baseUrl, "https://proxy.example/anthropic");
  assert.equal(models.providers.anthropic.models, undefined);
});
