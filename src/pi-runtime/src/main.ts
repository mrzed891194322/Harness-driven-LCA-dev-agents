#!/usr/bin/env node
/**
 * Harness Pi SDK runtime.
 *
 * Service mode (`--listen <socket-or-tcp>`): the project's single long-lived
 * runtime, started by `npm run dev` and stopped by `npm run stop`. A filesystem
 * path is a Unix domain socket; `tcp://127.0.0.1:<port>` is loopback TCP.
 * Clients (backend, workflow.py) speak NDJSON. When a client disconnects, the
 * sessions it created are released. It does not follow any parent. On Linux /
 * macOS, SIGTERM/SIGINT/SIGHUP stop it. On Windows, `runtime.shutdown` does the
 * same work (signals from another process do not run these handlers), then
 * sessions and MCP children are released and the listen address is dropped.
 *
 * Stdio mode (no flag): private child for tests and probes -- NDJSON on
 * stdin/stdout, logs on stderr, exits on stdin EOF, signals or parent loss.
 */
import {
  disposeAllSessions,
  handleRuntimeMethod,
  releaseSessionsOwnedBy,
  runtimeMode,
  setShutdownRequestHandler,
  setTransportInfo,
} from "./session_host.js";
import { emitEvent, startProtocolLoop } from "./protocol.js";
import { installLifecycle } from "./lifecycle.js";
import { parseListenEndpoint, removeEndpointRecord } from "./endpoint.js";
import { startSocketServer, type SocketServer } from "./server.js";

function listenPath(argv: string[]): string | null {
  const index = argv.indexOf("--listen");
  if (index < 0) return null;
  const value = argv[index + 1];
  if (!value || value.startsWith("--")) {
    process.stderr.write("[pi-runtime] --listen needs a socket path or tcp://127.0.0.1:<port>\n");
    process.exit(2);
  }
  try {
    return parseListenEndpoint(value).raw;
  } catch (error) {
    process.stderr.write(`[pi-runtime] ${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(2);
  }
}

const socketPath = listenPath(process.argv.slice(2));
const log = (line: string) => process.stderr.write(`${line}\n`);

log(
  `[pi-runtime] starting pid=${process.pid} ppid=${process.ppid} mode=${runtimeMode()} ` +
    `transport=${socketPath ? `socket ${socketPath}` : "stdio"}`,
);

if (socketPath) {
  await runService(socketPath);
} else {
  runStdio();
}

async function runService(listenAddress: string): Promise<void> {
  setTransportInfo({ transport: "socket", socket: listenAddress });
  let server: SocketServer | null = null;
  const lifecycle = installLifecycle({
    // A service outlives whoever launched it (dev.mjs exits right away).
    parentPollMs: 0,
    onShutdown: async () => {
      await server?.close();
      removeEndpointRecord(listenAddress);
      await disposeAllSessions();
    },
    log,
  });
  // Reply to runtime.shutdown first (the handler delays), then stop.
  setShutdownRequestHandler((reason) => void lifecycle.shutdown(reason));
  // One misbehaving session must not take every client's runtime down.
  process.on("unhandledRejection", (reason) => log(`[pi-runtime] unhandled rejection: ${String(reason)}`));
  process.on("uncaughtException", (error) => log(`[pi-runtime] uncaught exception: ${error.stack ?? String(error)}`));
  try {
    server = await startSocketServer({
      socketPath: listenAddress,
      onRequest: handleRuntimeMethod,
      onPeerClosed: async (peer) => {
        const released = await releaseSessionsOwnedBy(peer.id);
        if (released) log(`[pi-runtime] released ${released} session(s) of connection #${peer.id}`);
      },
      readyInfo: () => ({ mode: runtimeMode(), pid: process.pid }),
      log,
    });
  } catch (error) {
    log(`[pi-runtime] ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
  }
  log(`[pi-runtime] listening on ${listenAddress}`);
}

function runStdio(): void {
  setTransportInfo({ transport: "stdio", socket: null });
  const lifecycle = installLifecycle({
    onShutdown: () => disposeAllSessions(),
    log,
  });
  // Host gone mid-write (EPIPE): same as stdin EOF.
  process.stdout.on("error", () => void lifecycle.shutdown("stdout closed"));
  emitEvent("ready", { protocol: 1, mode: runtimeMode(), pid: process.pid });
  startProtocolLoop(handleRuntimeMethod, {
    onClose: () => void lifecycle.shutdown("stdin closed"),
  });
}
