import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createAgentSession, DefaultResourceLoader, ModelRuntime, SessionManager, SettingsManager } from "@earendil-works/pi-coding-agent";
import { Type, fauxProvider, fauxAssistantMessage, fauxToolCall, createAssistantMessageEventStream, type AssistantMessage } from "@earendil-works/pi-ai";
import { SettleGuard } from "./settle_guard.js";
import { installSubmitBoundary } from "./submit_boundary.js";

// Real installed AgentSession + extension hooks + SDK tool loop, with only the
// provider stream replaced. No HTTP, credentials, project workspace or live MCP.
async function harness(t: any, batches: AssistantMessage[], requireSubmit = true) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "submit-boundary-"));
  const file = path.join(dir, "submit.json");
  const guard = new SettleGuard({ submit_file: file, max_nudges: 0, max_turns: 100,
    timeout_min: 0, max_rejections: 5, model_retry_delays_s: [], require_submit: requireSubmit });
  const calls: string[] = [];
  const loader = new DefaultResourceLoader({ cwd: dir, agentDir: dir, noSkills: true,
    noPromptTemplates: true, noThemes: true, noContextFiles: true, systemPrompt: "offline test",
    extensionFactories: [(pi) => {
      pi.on("tool_call", (e, ctx) => guard.onToolCall(e.toolName, e.input, () => ctx.abort()));
      pi.on("tool_result", (_e, ctx) => { guard.onToolResult(() => ctx.abort()); });
      pi.on("turn_end", (e, ctx) => { guard.onTurnEnd(() => ctx.abort(), e.message as any); });
      pi.on("agent_before_settle", () => guard.beforeSettle());
    }] });
  await loader.reload();
  const modelRuntime = await ModelRuntime.create({ authPath: path.join(dir, "unused-auth.json"),
    modelsPath: null, modelsStorePath: path.join(dir, "catalog"), allowModelNetwork: false, refreshOnCreate: false });
  // Offline auth availability stub; no credential material is loaded or needed.
  modelRuntime.checkAuth = async () => ({}) as any;
  const { session } = await createAgentSession({ cwd: dir, agentDir: dir, modelRuntime,
    model: fauxProvider().getModel(), resourceLoader: loader,
    settingsManager: SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: false } }),
    sessionManager: SessionManager.inMemory(dir), tools: ["mcp__submit__submit", "work"],
    customTools: [
      { name: "mcp__submit__submit", label: "submit", description: "offline commit",
        parameters: Type.Object({ status: Type.String(), summary: Type.Optional(Type.String()) }),
        async execute(_id, input) {
          const args = input as { status: string; summary?: string };
          calls.push(args.status);
          await new Promise(r => setTimeout(r, 5));
          if (args.status === "throw") throw new Error("tool failed");
          if (args.status !== "invalid") fs.writeFileSync(file, JSON.stringify(args), { flag: "wx" });
          return { content: [{ type: "text", text: JSON.stringify({ accepted: args.status !== "invalid" }) }], details: {} };
        } },
      { name: "work", label: "work", description: "offline work", parameters: Type.Object({}),
        async execute() { calls.push("work"); return { content: [{ type: "text", text: "ok" }], details: {} }; } },
    ] });
  installSubmitBoundary(session.agent, guard);
  let requests = 0;
  session.agent.streamFunction = () => {
    const response = batches[requests++];
    if (!response) throw new Error("unexpected provider continuation");
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: response.stopReason as "stop", message: response });
    stream.end(response);
    return stream;
  };
  await session.bindExtensions({});
  t.after(async () => { await session.abort(); session.dispose(); fs.rmSync(dir, { recursive: true, force: true }); });
  async function run() { guard.begin(() => { void session.abort(); }); await session.prompt("offline"); guard.clear(); assert.equal(session.isIdle, true); }
  return { run, calls, file, guard, requests: () => requests };
}
const call = (status: string, summary = "dispatch") => fauxToolCall("mcp__submit__submit", { status, summary });
const batch = (...calls: ReturnType<typeof fauxToolCall>[]) => fauxAssistantMessage(calls, { stopReason: "toolUse" });

test("SDK: first accepted dispatch ends segment; alternating/changed-summary siblings never execute", { timeout: 5000 }, async t => {
  const h = await harness(t, [batch(fauxToolCall("work", {}), call("assign_executor"),
    call("assign_reviewer", "changed"), call("assign_executor", "different"), fauxToolCall("work", {}))]);
  await h.run();
  assert.deepEqual(h.calls, ["work", "assign_executor"]);
  assert.equal(h.requests(), 1);
  assert.equal(JSON.parse(fs.readFileSync(h.file, "utf8")).status, "assign_executor");
  assert.equal(h.guard.summary().log.filter(e => e.kind === "handoff").length, 1);
  assert.equal(h.guard.summary().abort_reason, "");
});

test("SDK: rejected/failed submit can be corrected; next host turn can dispatch again", { timeout: 5000 }, async t => {
  const h = await harness(t, [batch(call("invalid"), call("throw"), call("assign_executor"), call("assign_reviewer")),
    batch(call("assign_reviewer")), batch(call("approve"))]);
  await h.run();
  assert.deepEqual(h.calls, ["invalid", "throw", "assign_executor"]);
  fs.unlinkSync(h.file); // driver's archive boundary
  await h.run();
  assert.equal(JSON.parse(fs.readFileSync(h.file, "utf8")).status, "assign_reviewer");
  fs.unlinkSync(h.file);
  await h.run();
  assert.deepEqual(h.calls, ["invalid", "throw", "assign_executor", "assign_reviewer", "approve"]);
  assert.equal(h.requests(), 3);
});

test("SDK: assistant without submit completes ordinary multi-tool work", { timeout: 5000 }, async t => {
  const h = await harness(t, [batch(fauxToolCall("work", {}), fauxToolCall("work", {})), fauxAssistantMessage("finished")], false);
  await h.run();
  assert.deepEqual(h.calls, ["work", "work"]);
  assert.equal(h.requests(), 2);
  assert.equal(h.guard.summary().submitted, false);
});

test("SDK: required submit missing settles without inventing a handoff", { timeout: 5000 }, async t => {
  const h = await harness(t, [fauxAssistantMessage("I am done")]);
  await h.run();
  assert.equal(h.requests(), 1);
  assert.equal(h.guard.summary().submitted, false);
  assert.equal(h.guard.summary().log.at(-1)?.kind, "no_submit");
});
