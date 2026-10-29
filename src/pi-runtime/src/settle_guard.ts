/**
 * v5 end-of-node guard. Only an accepted submit (the submit tool wrote submit_file) ends an agent turn
 * normally. pi 1.3.0: `agent_before_settle` handlers return BoundaryResult `{ entries?, continue? }`;
 * returning `continue: true` with a custom_message entry makes pi run one more provider request.
 */
import fs from "node:fs";

export interface SettlePolicy {
  submit_file: string;
  max_nudges: number;
  max_turns: number;
  timeout_min: number;
  /** submit_rejections.jsonl of this node+agent (one line per rejected submit). */
  rejections_file?: string;
  /** Rejected submits on this node before it fails with too_many_rejections. */
  max_rejections: number;
  nudge_text?: string;
  /** Provider errors (stopReason "error", e.g. "Connection error.") retried per host turn, with these waits (s). */
  model_retry_delays_s: number[];
  node?: string;
  agent?: string;
  /** When false (assistant), turn may end without submit. Default true. */
  require_submit?: boolean;
  /** Consecutive identical tool+args calls before abort. 0 = off. Default 3 from host. */
  same_tool_limit?: number;
}

export interface SettleSummary {
  submitted: boolean;
  nudges: number;
  turns: number;
  abort_reason: "" | "max_turns" | "timeout" | "too_many_rejections" | "model_error" | "same_tool_limit";
  model_errors: number;
  rejections: number;
  log: { ts: string; kind: string; detail?: string }[];
}

export function settlePolicyOf(turnContext: Record<string, unknown> | undefined): SettlePolicy | null {
  const raw = turnContext?.settle as Partial<SettlePolicy> | undefined;
  if (!raw || typeof raw.submit_file !== "string" || !raw.submit_file) return null;
  return {
    submit_file: raw.submit_file,
    max_nudges: Number(raw.max_nudges ?? 2),
    max_turns: Number(raw.max_turns ?? 80),
    timeout_min: Number(raw.timeout_min ?? 120),
    rejections_file: typeof raw.rejections_file === "string" ? raw.rejections_file : undefined,
    max_rejections: Number(raw.max_rejections ?? 5),
    nudge_text: raw.nudge_text,
    node: typeof raw.node === "string" ? raw.node : undefined,
    agent: typeof raw.agent === "string" ? raw.agent : undefined,
    model_retry_delays_s: Array.isArray(raw.model_retry_delays_s) ? raw.model_retry_delays_s.map(Number) : [10, 30, 60],
    require_submit: raw.require_submit !== false,
    same_tool_limit: Number(raw.same_tool_limit ?? 0),
  };
}

export class SettleGuard {
  private nudges = 0;
  private turns = 0;
  private abortReason: SettleSummary["abort_reason"] = "";
  private timer: NodeJS.Timeout | null = null;
  private log: SettleSummary["log"] = [];
  private seenRejections = 0;
  private modelErrors = 0;
  private lastToolFp = "";
  private sameToolStreak = 0;
  /** Live listener for each log entry (I-31): pi-runtime streams it to the host as it happens. */
  notify: ((entry: { ts: string; kind: string; detail?: string }) => void) | null = null;
  private lastError = "";

  constructor(
    private policy: SettlePolicy,
    private exists: (file: string) => boolean = (f) => fs.existsSync(f),
    private countLines: (file: string) => number = (f) => {
      try {
        return fs.readFileSync(f, "utf8").split("\n").filter((l) => l.trim()).length;
      } catch {
        return 0;
      }
    },
    private sleep: (ms: number) => Promise<void> = (ms) => new Promise((r) => setTimeout(r, ms)),
  ) {}

  /** Rejected submits recorded for this node+agent so far (all rounds). */
  rejections(): number {
    return this.policy.rejections_file ? this.countLines(this.policy.rejections_file) : 0;
  }

  private tooManyRejections(): boolean {
    return this.policy.max_rejections > 0 && this.rejections() >= this.policy.max_rejections && !this.submitted();
  }

  /** Start of one host turn (session.run_turn): reset counters, arm the wall clock. */
  begin(abort: () => void): void {
    this.nudges = 0;
    this.turns = 0;
    this.abortReason = "";
    this.log = [];
    this.modelErrors = 0;
    this.lastError = "";
    this.lastToolFp = "";
    this.sameToolStreak = 0;
    this.seenRejections = this.rejections();
    this.clear();
    const ms = this.policy.timeout_min * 60_000;
    if (ms > 0 && Number.isFinite(ms)) {
      this.timer = setTimeout(() => this.abort("timeout", abort), ms);
      this.timer.unref?.();
    }
  }

  clear(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private note(kind: string, detail?: string): void {
    const entry = { ts: new Date().toISOString(), kind, detail };
    this.log.push(entry);
    try {
      this.notify?.(entry);
    } catch {
      // streaming is best effort; the entry is still in the summary log
    }
  }

  /** Consecutive identical tool calls (name+args). Returns block reason when limit hit. */
  onToolCall(toolName: string, input: Record<string, unknown>, abort?: () => void): { block: true; reason: string } | undefined {
    const limit = this.policy.same_tool_limit ?? 0;
    if (!limit || limit < 1) return undefined;
    let fp = toolName;
    try {
      fp = `${toolName}:${JSON.stringify(input, Object.keys(input).sort())}`;
    } catch {
      fp = `${toolName}:[unstringifiable]`;
    }
    if (fp === this.lastToolFp) this.sameToolStreak += 1;
    else {
      this.lastToolFp = fp;
      this.sameToolStreak = 1;
    }
    if (this.sameToolStreak >= limit) {
      const reason = `same_tool_limit: 连续 ${this.sameToolStreak} 次相同工具调用（${toolName}）`;
      this.abort("same_tool_limit", abort ?? (() => {}), reason);
      return { block: true, reason };
    }
    return undefined;
  }

  private abort(reason: "max_turns" | "timeout" | "too_many_rejections" | "same_tool_limit", abort: () => void, detail?: string): void {
    if (this.abortReason) return;
    this.abortReason = reason;
    this.note("abort", detail || reason);
    try {
      abort();
    } catch {
      // abort is best effort; the reason is recorded either way
    }
  }

  onTurnEnd(abort: () => void, message?: { stopReason?: string; errorMessage?: string }): void {
    this.lastError = message?.stopReason === "error" ? message.errorMessage || "provider error" : "";
    // Q1: a failed model request is a network problem, not agent work: it does not count toward max_turns.
    if (!this.lastError) this.turns += 1;
    if (this.tooManyRejections()) this.abort("too_many_rejections", abort);
    else if (this.turns >= this.policy.max_turns && !this.submitted()) this.abort("max_turns", abort);
  }

  submitted(): boolean {
    return this.exists(this.policy.submit_file);
  }

  /** agent_before_settle handler body. */
  async beforeSettle(): Promise<{ entries?: any[]; continue?: boolean } | undefined> {
    if (this.abortReason || this.submitted()) return undefined;
    if (this.policy.require_submit === false) return undefined; // assistant: no submit required
    if (this.lastError) {
      // A provider error is not a missing submit: retry after a wait without spending a nudge.
      const err = this.lastError;
      this.lastError = "";
      const delays = this.policy.model_retry_delays_s;
      if (this.modelErrors >= delays.length) {
        this.abortReason = "model_error";
        const who = [this.policy.node, this.policy.agent].filter(Boolean).join(" / ") || "当前节点";
        // Q14: retries exhausted -> one clear Chinese error (node, retry count, last error) in events and UI.
        this.note("abort", `model_error: ${who} 的模型请求重试 ${delays.length} 次后仍失败，节点停止。最后一次错误：${err}`);
        return undefined;
      }
      const wait = delays[this.modelErrors];
      this.modelErrors += 1;
      this.note("model_retry", `${this.modelErrors}/${delays.length} after ${wait}s: ${err}`);
      await this.sleep(wait * 1000);
      return {
        entries: [{ type: "custom_message", customType: "workflow_nudge", content: `上一次模型请求失败（${err}）。从中断处继续完成任务，完成后调用 submit。`, display: true }],
        continue: true,
      };
    }
    if (this.tooManyRejections()) {
      this.abortReason = "too_many_rejections";
      this.note("abort", "too_many_rejections");
      return undefined;
    }
    const now = this.rejections();
    if (now > this.seenRejections) {
      // A rejected submit is not a missing submit: remind without spending a nudge.
      this.seenRejections = now;
      this.note("rejected_retry", `rejections=${now}/${this.policy.max_rejections}`);
      return {
        entries: [{ type: "custom_message", customType: "workflow_nudge", content: `submit 被拒绝（${now}/${this.policy.max_rejections} 次）。按返回的错误修正交付物后再调用 submit；达到上限节点会失败。`, display: true }],
        continue: true,
      };
    }
    if (this.nudges >= this.policy.max_nudges) {
      this.note("no_submit", `nudges=${this.nudges}`);
      return undefined;
    }
    this.nudges += 1;
    this.note("nudge", String(this.nudges));
    const text =
      this.policy.nudge_text ||
      `你还没有成功调用 submit（第 ${this.nudges}/${this.policy.max_nudges} 次提醒）。完成交付物后调用 submit；未用到的可选参数请省略（不要传 null）。若 submit 返回校验错误，先修正再重新提交。`;
    return {
      entries: [{ type: "custom_message", customType: "workflow_nudge", content: text, display: true }],
      continue: true,
    };
  }

  summary(): SettleSummary {
    return {
      submitted: this.submitted(),
      nudges: this.nudges,
      turns: this.turns,
      abort_reason: this.abortReason,
      rejections: this.rejections(),
      model_errors: this.modelErrors,
      log: [...this.log],
    };
  }
}
