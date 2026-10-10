/**
 * Path whitelist for Pi worker file tools (issue #27, REFACTOR_PLAN §7).
 *
 * read/grep/find/ls must stay inside the read roots; write/edit inside the write roots.
 * Paths are resolved to absolute real paths (symlinks followed; for targets that do not
 * exist yet, the deepest existing ancestor is realpath'd) before comparison, so `../`
 * and symlink escapes are caught. bash is not blocked: every command is logged and
 * paths outside the read scope are flagged (a real sandbox is future work).
 *
 * Scopes come only from the launch spec (core parses harness/specs/<stage>/permissions.yaml).
 * deniedWriteGlobs (official deliverable paths only spec_mcp may write) beat writeGlobs.
 * Empty scopes deny everything (fail closed).
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const READ_TOOLS = new Set(["read", "grep", "find", "ls"]);
export const WRITE_TOOLS = new Set(["write", "edit"]);

export interface GuardRecord {
  ts: string;
  session_key: string;
  tool: string;
  action: "denied" | "bash_command";
  requested_path?: string;
  resolved_path?: string;
  reason?: string;
  command?: string;
  out_of_scope?: { requested: string; resolved: string }[];
}

export interface PathGuardOptions {
  sessionKey: string;
  cwd: string;
  readGlobs: string[];
  writeGlobs: string[];
  /** Write-denied even inside writeGlobs (spec_mcp-owned deliverable paths). */
  deniedWriteGlobs?: string[];
  /** Where denial / bash records are appended (JSONL). */
  logFile?: string;
  /** Extra live sink (e.g. turn.event to the host). */
  notify?: (record: GuardRecord) => void;
}

/** Real path of `p`; for a missing target, realpath the deepest existing ancestor. */
export function realResolve(p: string): string {
  let current = path.resolve(p);
  const rest: string[] = [];
  for (;;) {
    try {
      const real = fs.realpathSync.native(current);
      return rest.length ? path.join(real, ...rest.reverse()) : real;
    } catch {
      const parent = path.dirname(current);
      if (parent === current) {
        return path.resolve(p);
      }
      rest.push(path.basename(current));
      current = parent;
    }
  }
}

/** Mirror Pi's own path handling: strip a leading '@', expand '~', resolve against cwd. */
export function toAbsolute(raw: string, cwd: string): string {
  let p = raw.trim();
  if (p.startsWith("@")) p = p.slice(1);
  if (p === "~") p = os.homedir();
  else if (p.startsWith("~/")) p = path.join(os.homedir(), p.slice(2));
  return path.resolve(cwd, p);
}

/** "<dir>/**" (or "<dir>") becomes the real path of <dir>. */
export function rootsFromGlobs(globs: string[]): string[] {
  return globs
    .map((g) => g.replace(/\/\*\*$/, "").replace(/\/+$/, "") || "/")
    .map((g) => realResolve(g));
}

export function isInside(target: string, roots: string[]): boolean {
  return roots.some((root) => {
    const rel = path.relative(root, target);
    return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
  });
}

export interface CheckResult {
  allowed: boolean;
  requested: string;
  resolved: string;
  reason?: string;
}

export class PathGuard {
  readonly readRoots: string[];
  readonly writeRoots: string[];
  readonly deniedWriteRoots: string[];

  constructor(private readonly opts: PathGuardOptions) {
    this.readRoots = rootsFromGlobs(opts.readGlobs);
    // Anything writable is also readable.
    this.writeRoots = rootsFromGlobs(opts.writeGlobs);
    this.deniedWriteRoots = rootsFromGlobs(opts.deniedWriteGlobs ?? []);
  }

  check(tool: string, rawPath: string | undefined): CheckResult {
    const requested = rawPath && rawPath.trim() ? rawPath : ".";
    const resolved = realResolve(toAbsolute(requested, this.opts.cwd));
    if (WRITE_TOOLS.has(tool)) {
      if (isInside(resolved, this.deniedWriteRoots)) {
        return {
          allowed: false,
          requested,
          resolved,
          reason: "这是正式交付路径，只能由 spec_mcp 写入：先把草稿写在 workspace 其他位置，再调用 spec_mcp 的 submit 提交",
        };
      }
      if (isInside(resolved, this.writeRoots)) {
        return { allowed: true, requested, resolved };
      }
      return {
        allowed: false,
        requested,
        resolved,
        reason: `写入路径不在允许范围内（允许：${this.writeRoots.join(", ") || "无"}）`,
      };
    }
    const roots = [...this.readRoots, ...this.writeRoots];
    if (isInside(resolved, roots)) {
      return { allowed: true, requested, resolved };
    }
    return {
      allowed: false,
      requested,
      resolved,
      reason: `读取路径不在允许范围内（允许：${this.readRoots.join(", ") || "无"}）`,
    };
  }

  /** Default directory for grep/find/ls called without a path: first read root. */
  defaultSearchRoot(): string | null {
    return this.readRoots[0] ?? null;
  }

  record(entry: Omit<GuardRecord, "ts" | "session_key">): void {
    const full: GuardRecord = { ts: new Date().toISOString(), session_key: this.opts.sessionKey, ...entry };
    if (this.opts.logFile) {
      try {
        fs.mkdirSync(path.dirname(this.opts.logFile), { recursive: true });
        fs.appendFileSync(this.opts.logFile, JSON.stringify(full) + "\n");
      } catch {
        // logging is best effort
      }
    }
    try {
      this.opts.notify?.(full);
    } catch {
      // ignore
    }
  }

  /** Returns a block result for out-of-scope file tool calls, or undefined to allow. */
  onToolCall(toolName: string, input: Record<string, unknown>): { block: true; reason: string } | undefined {
    if (toolName === "bash") {
      const command = String(input.command ?? "");
      const flagged = this.bashOutOfScope(command);
      this.record({ tool: "bash", action: "bash_command", command, out_of_scope: flagged.length ? flagged : undefined });
      return undefined;
    }
    if (!READ_TOOLS.has(toolName) && !WRITE_TOOLS.has(toolName)) {
      return undefined;
    }
    let raw = typeof input.path === "string" ? input.path : undefined;
    if (!raw && READ_TOOLS.has(toolName) && toolName !== "read") {
      // grep/find/ls default to cwd (project root); point them at the workspace instead.
      const fallback = this.defaultSearchRoot();
      if (fallback) {
        input.path = fallback;
        raw = fallback;
      }
    }
    const result = this.check(toolName, raw);
    if (result.allowed) return undefined;
    this.record({
      tool: toolName,
      action: "denied",
      requested_path: result.requested,
      resolved_path: result.resolved,
      reason: result.reason,
    });
    return {
      block: true,
      reason: `权限拒绝：${toolName} ${result.requested} -> ${result.resolved}。${result.reason}。其余资料已由宿主注入提示词，不需要自己读取。`,
    };
  }

  /** Path-like tokens in a shell command that resolve outside the read scope. */
  bashOutOfScope(command: string): { requested: string; resolved: string }[] {
    const out: { requested: string; resolved: string }[] = [];
    const tokens = command.match(/(?:[^\s"'`;|&<>()]+)/g) ?? [];
    for (let token of tokens) {
      token = token.replace(/^[A-Za-z_][A-Za-z0-9_]*=/, "");
      if (!(token.includes("/") || token === ".." || token.startsWith("~"))) continue;
      if (/^[a-z]+:\/\//i.test(token)) continue;
      // Interpreter / system binaries are not data reads.
      if (/^\/(usr|bin|sbin|lib|lib64|etc\/alternatives|dev\/null|proc\/self)\b/.test(token)) continue;
      const resolved = realResolve(toAbsolute(token, this.opts.cwd));
      if (!isInside(resolved, [...this.readRoots, ...this.writeRoots])) {
        out.push({ requested: token, resolved });
      }
    }
    return out;
  }
}
