import { AsyncLocalStorage } from "node:async_hooks";
import readline from "node:readline";
import type { ProtocolEvent, ProtocolRequest, ProtocolResponse } from "./types.js";

export type RequestHandler = (
  method: string,
  params: Record<string, unknown>,
) => Promise<unknown>;

export type HandoffSubmitHandler = (
  params: Record<string, unknown>,
) => Promise<unknown>;

/**
 * One client of the runtime. In stdio mode there is exactly one (the process's
 * own stdin/stdout); in service mode every socket connection is a peer.
 */
export interface Peer {
  readonly id: number;
  /** Free-form label the client reports with `client.hello` (e.g. "backend pid=1"). */
  label: string;
  readonly connectedAt: string;
  send(payload: unknown): void;
}

const peers = new Map<number, Peer>();
const currentPeerStore = new AsyncLocalStorage<Peer>();

export function registerPeer(peer: Peer): void {
  peers.set(peer.id, peer);
}

export function unregisterPeer(peer: Peer): void {
  peers.delete(peer.id);
}

export function listPeers(): Peer[] {
  return [...peers.values()];
}

/** The peer whose request is being handled (undefined outside a request). */
export function currentPeer(): Peer | undefined {
  return currentPeerStore.getStore();
}

function writeStdout(payload: unknown): void {
  process.stdout.write(JSON.stringify(payload) + "\n");
}

/** The stdio peer (id 0) used when the runtime is a private child process. */
export const stdioPeer: Peer = {
  id: 0,
  label: "stdio",
  connectedAt: new Date().toISOString(),
  send: writeStdout,
};

/**
 * Send an event to `peer`, else to the peer whose request we are serving, else to
 * every connected peer (consumers filter by session_key / login_id).
 */
export function emitEvent(
  event: string,
  data?: Record<string, unknown>,
  peer: Peer | undefined = currentPeer(),
): void {
  const payload: ProtocolEvent = { type: "event", event, data };
  if (peer) {
    peer.send(payload);
    return;
  }
  if (!peers.size) {
    writeStdout(payload);
    return;
  }
  for (const p of peers.values()) p.send(payload);
}

export function emitResponse(res: ProtocolResponse, peer: Peer = stdioPeer): void {
  peer.send(res);
}

export interface ProtocolLoopOptions {
  onHandoffSubmit?: HandoffSubmitHandler;
  /** Called once when the input reaches EOF (host closed the pipe / socket). */
  onClose?: () => void;
  input?: NodeJS.ReadableStream;
  /** Who receives responses and request-scoped events (default: stdout). */
  peer?: Peer;
}

export function startProtocolLoop(
  onRequest: RequestHandler,
  options: ProtocolLoopOptions = {},
): void {
  const { onHandoffSubmit, onClose } = options;
  const peer = options.peer ?? stdioPeer;
  const rl = readline.createInterface({
    input: options.input ?? process.stdin,
    crlfDelay: Infinity,
  });
  rl.on("close", () => onClose?.());
  rl.on("line", (line) => {
    let parsed: ProtocolRequest;
    try {
      parsed = JSON.parse(line) as ProtocolRequest;
    } catch {
      return;
    }
    if (parsed.type !== "req" || !parsed.id || !parsed.method) {
      return;
    }
    const params = (parsed.params ?? {}) as Record<string, unknown>;
    void currentPeerStore.run(peer, async () => {
      try {
        let result: unknown;
        if (parsed.method === "handoff.submit" && onHandoffSubmit) {
          result = await onHandoffSubmit(params);
        } else {
          result = await onRequest(parsed.method, params);
        }
        emitResponse({ type: "res", id: parsed.id, ok: true, result }, peer);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        emitResponse(
          {
            type: "res",
            id: parsed.id,
            ok: false,
            error: { code: "runtime_error", message },
          },
          peer,
        );
      }
    });
  });
}
