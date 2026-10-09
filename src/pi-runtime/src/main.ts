#!/usr/bin/env node
/**
 * Harness Pi SDK runtime — NDJSON on stdin/stdout, logs on stderr.
 *
 * Lifetime is bound to the host: stdin EOF, SIGTERM/SIGINT/SIGHUP, or losing the
 * parent process all dispose every session (closing MCP children) and exit.
 */
import { disposeAllSessions, handleRuntimeMethod, runtimeMode } from "./session_host.js";
import { emitEvent, startProtocolLoop } from "./protocol.js";
import { installLifecycle } from "./lifecycle.js";

process.stderr.write(
  `[pi-runtime] starting pid=${process.pid} ppid=${process.ppid} mode=${runtimeMode()}\n`,
);

const lifecycle = installLifecycle({
  onShutdown: () => disposeAllSessions(),
});

// Host gone mid-write (EPIPE): same as stdin EOF.
process.stdout.on("error", () => void lifecycle.shutdown("stdout closed"));

emitEvent("ready", { protocol: 1, mode: runtimeMode() });

startProtocolLoop(handleRuntimeMethod, {
  onClose: () => void lifecycle.shutdown("stdin closed"),
});
