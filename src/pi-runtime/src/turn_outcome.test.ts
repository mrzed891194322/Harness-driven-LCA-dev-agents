import assert from "node:assert/strict";
import test from "node:test";
import { TurnObserver, classifyError } from "./turn_outcome.js";

const failed = (msg = "Connection error.") => ({
  type: "message_end",
  message: { role: "assistant", stopReason: "error", errorMessage: msg, usage: { input: 0, output: 0 }, content: [] },
});

test("native: SDK retries exhausted -> model connection failure", () => {
  const o = new TurnObserver();
  o.handle(failed());
  for (let i = 1; i <= 4; i++) {
    o.handle({ type: "auto_retry_start", attempt: i, maxAttempts: 4, delayMs: 10, errorMessage: "Connection error." });
    o.handle(failed());
  }
  o.handle({ type: "auto_retry_end", success: false, attempt: 4, finalError: "Connection error." });
  const r = o.outcome();
  assert.equal(r.model_connection_failure, true);
  assert.equal(r.connection_signal, "native");
  assert.equal(r.error_kind, "connection");
  assert.equal(r.sdk_retries, 4);
  assert.equal(r.tool_calls, 0);
  assert.equal(r.stop_reason, "error");
});

test("fallback: no retry, last stopReason error", () => {
  const o = new TurnObserver();
  o.handle(failed("503 service unavailable"));
  const r = o.outcome();
  assert.equal(r.connection_signal, "fallback");
  assert.equal(r.error_kind, "5xx");
  assert.equal(r.model_connection_failure, true);
});

test("retry recovered -> ok with tokens and tool counts", () => {
  const o = new TurnObserver();
  o.handle(failed());
  o.handle({ type: "auto_retry_start", attempt: 1 });
  o.handle({ type: "tool_execution_end", toolCallId: "a", toolName: "read", isError: false });
  o.handle({ type: "message_end", message: { role: "assistant", stopReason: "stop", usage: { input: 100, output: 20 } } });
  o.handle({ type: "auto_retry_end", success: true, attempt: 1 });
  const r = o.outcome();
  assert.equal(r.model_connection_failure, false);
  assert.equal(r.error_kind, "none");
  assert.equal(r.input_tokens, 100);
  assert.equal(r.tool_calls, 1);
});

test("failure after successful tools is not reported as connection failure", () => {
  const o = new TurnObserver();
  o.handle({ type: "tool_execution_end", isError: false });
  o.handle(failed());
  o.handle({ type: "auto_retry_end", success: false, finalError: "Connection error." });
  assert.equal(o.outcome().model_connection_failure, false);
});

test("classifyError", () => {
  assert.equal(classifyError("429 Too Many Requests"), "429");
  assert.equal(classifyError("Request timed out"), "timeout");
  assert.equal(classifyError("fetch failed"), "connection");
  assert.equal(classifyError(null), "none");
  assert.equal(classifyError("invalid api key"), "other");
});
