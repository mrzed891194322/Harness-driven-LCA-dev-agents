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
  /** submit_rejections.jsonl of this node+role (one line per rejected submit). */
  rejections_file?: string;
  /** Rejected submits on this node before it fails with too_many_rejections. */
  max_rejections: number;
  nudge_text?: string;
}

export interface SettleSummary {
  submitted: boolean;
  nudges: number;
  turns: number;
  abort_reason: "" | "max_turns" | "timeout" | "too_many_rejections";
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
    timeout_min: Number(raw.timeout_min ?? 45),
    rejections_file: typeof raw.rejections_file === "string" ? raw.rejections_file : undefined,
    max_rejections: Number(raw.max_rejections ?? 5),
    nudge_text: raw.nudge_text,
  };
}

export class SettleGuard {
  private nudges = 0;
  private turns = 0;
  private abortReason: SettleSummary["abort_reason"] = "";
  private timer: NodeJS.Timeout | null = null;
  private log: SettleSummary["log"] = [];
  private seenRejections = 0;

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
  ) {}

  /** Rejected submits recorded for this node+role so far (all rounds). */
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
    this.log.push({ ts: new Date().toISOString(), kind, detail });
  }

  private abort(reason: "max_turns" | "timeout" | "too_many_rejections", abort: () => void): void {
    if (this.abortReason) return;
    this.abortReason = reason;
    this.note("abort", reason);
    try {
      abort();
    } catch {
      // abort is best effort; the reason is recorded either way
    }
  }

  onTurnEnd(abort: () => void): void {
    this.turns += 1;
    if (this.tooManyRejections()) this.abort("too_many_rejections", abort);
    else if (this.turns >= this.policy.max_turns && !this.submitted()) this.abort("max_turns", abort);
  }

  submitted(): boolean {
    return this.exists(this.policy.submit_file);
  }

  /** agent_before_settle handler body. */
  beforeSettle(): { entries?: any[]; continue?: boolean } | undefined {
    if (this.abortReason || this.submitted()) return undefined;
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
        entries: [{ type: "custom_message", customType: "v5_nudge", content: `submit 被拒绝（${now}/${this.policy.max_rejections} 次）。按返回的错误修正交付物后再调用 submit；达到上限节点会失败。`, display: true }],
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
      `你还没有成功调用 submit（第 ${this.nudges}/${this.policy.max_nudges} 次提醒）。完成交付物后调用 submit；若 submit 返回校验错误，先修正再重新提交。`;
    return {
      entries: [{ type: "custom_message", customType: "v5_nudge", content: text, display: true }],
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
      log: [...this.log],
    };
  }
}
