#!/usr/bin/env node
/**
 * Harness Pi SDK runtime — NDJSON on stdin/stdout, logs on stderr.
 */
import { handleRuntimeMethod } from "./session_host.js";
import { emitEvent, startProtocolLoop } from "./protocol.js";

process.stderr.write(
  `[pi-runtime] starting pid=${process.pid} mock=${process.env.PI_RUNTIME_MOCK === "1"}\n`,
);

emitEvent("ready", { protocol: 1 });

startProtocolLoop(handleRuntimeMethod);
