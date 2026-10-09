/**
 * Process lifecycle for pi-runtime.
 *
 * Service mode (the project's single runtime, `--listen`): only SIGTERM/SIGINT/
 * SIGHUP stop it (`npm run stop`); parent polling is disabled.
 * Stdio mode (private child for tests/probes): also stops when stdin closes or
 * the parent process disappears (re-parented, e.g. to systemd).
 * Either way every live session is disposed first, closing its MCP servers.
 */

/** Minimal surface of a Pi AgentSession needed for a clean shutdown. */
export interface ShutdownablePiSession {
  abort(): Promise<void> | void;
  dispose(): void;
  readonly extensionRunner?: {
    hasHandlers(event: string): boolean;
    emit(event: unknown): Promise<unknown> | unknown;
  };
}

/**
 * Dispose a Pi session the way AgentSessionRuntime.dispose() does: abort the turn,
 * emit `session_shutdown` (the MCP extension closes its server connections, which
 * stops the stdio child processes), then dispose. `session.dispose()` alone does
 * NOT emit session_shutdown, which is why MCP children used to leak (ISSUES #22).
 */
export async function shutdownPiSession(session: ShutdownablePiSession): Promise<void> {
  try {
    await session.abort();
  } catch {
    // keep going: shutdown must not be blocked by a failing abort
  }
  try {
    const runner = session.extensionRunner;
    if (runner?.hasHandlers("session_shutdown")) {
      await runner.emit({ type: "session_shutdown", reason: "quit" });
    }
  } catch {
    // ignore
  }
  try {
    session.dispose();
  } catch {
    // ignore
  }
}

export interface LifecycleOptions {
  /** Release every live session (closes MCP children). */
  onShutdown: (reason: string) => Promise<void>;
  /** Max time to wait for onShutdown before exiting anyway. */
  graceMs?: number;
  /** How often to check whether the parent process is still ours (0 disables). */
  parentPollMs?: number;
  exit?: (code: number) => void;
  log?: (line: string) => void;
}

export interface Lifecycle {
  shutdown(reason: string): Promise<void>;
  readonly stopping: boolean;
}

export function installLifecycle(options: LifecycleOptions): Lifecycle {
  const graceMs = options.graceMs ?? 8000;
  const exit = options.exit ?? ((code: number) => process.exit(code));
  const log = options.log ?? ((line: string) => process.stderr.write(line + "\n"));
  let stopping = false;

  async function shutdown(reason: string): Promise<void> {
    if (stopping) return;
    stopping = true;
    log(`[pi-runtime] shutting down pid=${process.pid} reason=${reason}`);
    let timer: NodeJS.Timeout | undefined;
    await Promise.race([
      options.onShutdown(reason).catch((error: unknown) => {
        log(`[pi-runtime] shutdown error: ${error instanceof Error ? error.message : String(error)}`);
      }),
      new Promise<void>((resolve) => {
        timer = setTimeout(() => {
          log(`[pi-runtime] shutdown grace ${graceMs}ms elapsed; exiting anyway`);
          resolve();
        }, graceMs);
      }),
    ]);
    if (timer) clearTimeout(timer);
    exit(0);
  }

  for (const signal of ["SIGTERM", "SIGINT", "SIGHUP"] as const) {
    process.on(signal, () => void shutdown(signal));
  }

  const pollMs = options.parentPollMs ?? 2000;
  if (pollMs > 0 && process.platform !== "win32") {
    const parent = process.ppid;
    const timer = setInterval(() => {
      if (process.ppid !== parent) void shutdown(`parent ${parent} exited`);
    }, pollMs);
    timer.unref();
  }

  return {
    shutdown,
    get stopping() {
      return stopping;
    },
  };
}
