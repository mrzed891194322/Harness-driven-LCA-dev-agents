import assert from "node:assert/strict";
import http from "node:http";
import type { AddressInfo } from "node:net";
import test from "node:test";
import {
  collectServedModelIds,
  declaredEndpoint,
  modelIsServed,
  probeServedModelIds,
  probeUrls,
} from "./live_models.js";

test("declaredEndpoint ignores catalog baseUrl overrides without models", () => {
  const declared = declaredEndpoint(
    {
      providers: {
        openai: { baseUrl: "https://api.example.test/" },
        ollama: {
          baseUrl: "http://localhost:11434/v1",
          api: "openai-completions",
          apiKey: "local",
          models: [{ id: "qwen2.5-coder:7b", name: "本地 Ollama" }],
        },
      },
    },
    "openai",
  );
  assert.equal(declared, null);
});

test("probeUrls cover OpenAI-compatible models and Ollama tags", () => {
  assert.deepEqual(probeUrls("http://localhost:11434/v1"), [
    "http://localhost:11434/v1/models",
    "http://localhost:11434/api/tags",
  ]);
  assert.deepEqual(probeUrls("not-a-url"), []);
});

test("configured model id is loadable only when the endpoint lists it", () => {
  const served = collectServedModelIds({
    models: [{ name: "llama3.2:3b", model: "llama3.2:3b" }],
  });
  assert.equal(modelIsServed(served, "qwen2.5-coder:7b"), false);
  assert.equal(modelIsServed(served, "llama3.2:3b"), true);
  assert.equal(modelIsServed(new Set(["llama3.2"]), "llama3.2:latest"), true);
});

test("probe drops a declared model the server does not serve", async () => {
  const server = http.createServer((req, res) => {
    if (req.url === "/v1/models") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ data: [{ id: "llama3.2:3b" }] }));
      return;
    }
    res.writeHead(404);
    res.end();
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
  try {
    const { port } = server.address() as AddressInfo;
    const probe = await probeServedModelIds(`http://127.0.0.1:${port}/v1`, "local");
    assert.equal(probe.ok, true);
    if (!probe.ok) return;
    assert.equal(modelIsServed(probe.ids, "qwen2.5-coder:7b"), false);
    assert.equal(modelIsServed(probe.ids, "llama3.2:3b"), true);
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});

test("probe reports an unreachable endpoint instead of trusting the saved id", async () => {
  const probe = await probeServedModelIds("http://127.0.0.1:1/v1", "local");
  assert.equal(probe.ok, false);
  if (probe.ok) return;
  assert.match(probe.message, /无法连接端点/);
});
