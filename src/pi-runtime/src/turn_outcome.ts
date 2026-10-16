/**
 * Per-turn outcome tracking for session.run_turn.
 *
 * Primary (native) model-connection signal: the pi SDK's AgentSessionEvent
 * `auto_retry_end` with `success: false` and `finalError`
 * (@earendil-works/pi-coding-agent dist/core/agent-session.d.ts). AgentSession
 * emits it from `_handlePostAgentRun` once its own auto-retry budget is spent on
 * a retryable assistant error (classified by pi-ai `isRetryableAssistantError`),
 * and `session.prompt()` then resolves normally instead of throwing.
 * Fallback (no retry ran, e.g. retry disabled / non-retryable): the last
 * assistant message has stopReason "error" | "aborted" with an errorMessage.
 */

export type ErrorKind = "connection" | "timeout" | "429" | "5xx" | "none" | "other";

export interface TurnOutcome {
  stop_reason: string | null;
  error_kind: ErrorKind;
  error_message: string | null;
  input_tokens: number;
  output_tokens: number;
  tool_calls: number;
  tool_calls_ok: number;
  /** pi SDK auto_retry_start count in this turn (recovered or not). */
  sdk_retries: number;
  /** "native" = auto_retry_end(success=false); "fallback" = last stopReason. */
  connection_signal: "native" | "fallback" | null;
  model_connection_failure: boolean;
}

export function classifyError(message: string | null | undefined): ErrorKind {
  if (!message) return "none";
  const m = message.toLowerCase();
  if (/\b429\b|rate.?limit|too many requests/.test(m)) return "429";
  if (/\b5\d\d\b|overloaded|service.?unavailable|server.?error|internal.?error|bad gateway/.test(m)) return "5xx";
  if (/timed? ?out|timeout|etimedout/.test(m)) return "timeout";
  if (
    /connection|network|fetch failed|socket|econn|enotfound|eai_again|getaddrinfo|other side closed|terminated|ended without|stream ended|upstream|websocket|retry cancelled/.test(m)
  )
    return "connection";
  return "other";
}

export class TurnObserver {
  private stopReason: string | null = null;
  private lastError: string | null = null;
  private input = 0;
  private output = 0;
  private toolCalls = 0;
  private toolOk = 0;
  private retries = 0;
  private retryFailed: string | null = null;
  private retrySucceeded = false;

  handle(ev: any): void {
    if (!ev || typeof ev !== "object") return;
    switch (ev.type) {
      case "auto_retry_start":
        this.retries += 1;
        break;
      case "auto_retry_end":
        if (ev.success === false) this.retryFailed = String(ev.finalError ?? "Unknown error");
        else this.retrySucceeded = true;
        break;
      case "tool_execution_end":
        this.toolCalls += 1;
        if (!ev.isError) this.toolOk += 1;
        break;
      case "message_end": {
        const msg = ev.message;
        if (msg && msg.role === "assistant") {
          this.stopReason = msg.stopReason ?? null;
          this.lastError = msg.errorMessage ?? null;
          this.input += Number(msg.usage?.input ?? 0) || 0;
          this.output += Number(msg.usage?.output ?? 0) || 0;
        }
        break;
      }
    }
  }

  outcome(): TurnOutcome {
    let signal: TurnOutcome["connection_signal"] = null;
    let errorMessage: string | null = null;
    if (this.retryFailed !== null && this.retryFailed !== "Retry cancelled") {
      signal = "native";
      errorMessage = this.retryFailed;
    } else if (this.stopReason === "error" || this.stopReason === "aborted") {
      errorMessage = this.lastError ?? (this.stopReason === "aborted" ? "aborted" : "Unknown error");
      const kind = classifyError(errorMessage);
      if (this.stopReason === "error" && kind !== "other" && kind !== "none") signal = "fallback";
    }
    const kind = errorMessage ? classifyError(errorMessage) : "none";
    return {
      stop_reason: this.stopReason,
      error_kind: kind,
      error_message: errorMessage,
      input_tokens: this.input,
      output_tokens: this.output,
      tool_calls: this.toolCalls,
      tool_calls_ok: this.toolOk,
      sdk_retries: this.retries,
      connection_signal: signal,
      // Only a turn that achieved nothing is reported as a connection failure;
      // a turn with successful tools keeps its progress and goes through the
      // normal handoff checks.
      model_connection_failure: signal !== null && this.toolOk === 0,
    };
  }
}
