/**
 * Service mode: one long-lived pi-runtime for the whole project (ISSUES #23).
 * Linux / macOS listen on a Unix domain socket. Native Windows listens on
 * loopback TCP (`tcp://127.0.0.1:<port>`). Every connection is a peer speaking
 * the same NDJSON protocol as stdio mode; responses and request-scoped events
 * go back to the connection that asked. When a connection closes, the sessions
 * it created are released (so a crashed workflow.py cannot leak MCP servers).
 */
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { connectTarget, parseListenEndpoint } from "./endpoint.js";
import {
  type Peer,
  type RequestHandler,
  registerPeer,
  startProtocolLoop,
  unregisterPeer,
} from "./protocol.js";

export interface SocketServerOptions {
  socketPath: string;
  onRequest: RequestHandler;
  /** Release everything the peer owned; called once per closed connection. */
  onPeerClosed: (peer: Peer) => Promise<void> | void;
  /** Extra fields for the `ready` event every connection receives first. */
  readyInfo?: () => Record<string, unknown>;
  log?: (line: string) => void;
}

export interface SocketServer {
  readonly socketPath: string;
  close(): Promise<void>;
}

/** Is something already accepting connections on this unix path or `tcp://` address? */
export function socketInUse(socketPath: string, timeoutMs = 1000): Promise<boolean> {
  return new Promise((resolve) => {
    let target: ReturnType<typeof connectTarget>;
    try {
      target = connectTarget(socketPath);
    } catch {
      resolve(false);
      return;
    }
    if ("path" in target && target.path && !fs.existsSync(target.path)) {
      resolve(false);
      return;
    }
    const probe = net.connect(target);
    const done = (value: boolean) => {
      probe.destroy();
      resolve(value);
    };
    probe.setTimeout(timeoutMs, () => done(false));
    probe.once("connect", () => done(true));
    probe.once("error", () => done(false));
  });
}

export async function startSocketServer(options: SocketServerOptions): Promise<SocketServer> {
  const { socketPath, onRequest, onPeerClosed } = options;
  const log = options.log ?? ((line: string) => process.stderr.write(line + "\n"));
  const endpoint = parseListenEndpoint(socketPath);
  if (endpoint.kind === "unix") {
    fs.mkdirSync(path.dirname(endpoint.path), { recursive: true });
    if (fs.existsSync(endpoint.path)) {
      if (await socketInUse(endpoint.raw)) {
        throw new Error(`pi-runtime 已在运行（${endpoint.path} 有人监听）；只允许一个 runtime`);
      }
      fs.rmSync(endpoint.path, { force: true }); // stale file from a killed runtime
    }
  } else if (await socketInUse(endpoint.raw)) {
    throw new Error(`pi-runtime 已在运行（${endpoint.raw} 有人监听）；只允许一个 runtime`);
  }

  let nextId = 1;
  const sockets = new Set<net.Socket>();
  const server = net.createServer((socket) => {
    sockets.add(socket);
    const peer: Peer = {
      id: nextId++,
      label: "",
      connectedAt: new Date().toISOString(),
      send(payload: unknown) {
        if (socket.destroyed || !socket.writable) return;
        socket.write(JSON.stringify(payload) + "\n");
      },
    };
    registerPeer(peer);
    log(`[pi-runtime] connection #${peer.id} opened`);
    socket.on("error", () => {
      // reset by the client; "close" follows
    });
    let closed = false;
    const finish = () => {
      if (closed) return;
      closed = true;
      sockets.delete(socket);
      unregisterPeer(peer);
      log(`[pi-runtime] connection #${peer.id} closed${peer.label ? ` (${peer.label})` : ""}`);
      void Promise.resolve(onPeerClosed(peer)).catch((error: unknown) => {
        log(`[pi-runtime] releasing connection #${peer.id} failed: ${String(error)}`);
      });
    };
    socket.on("close", finish);
    peer.send({
      type: "event",
      event: "ready",
      data: { protocol: 1, connection_id: peer.id, ...(options.readyInfo?.() ?? {}) },
    });
    startProtocolLoop(onRequest, { input: socket, peer, onClose: finish });
  });

  await new Promise<void>((resolve, reject) => {
    const onListening = () => {
      server.off("error", reject);
      resolve();
    };
    server.once("error", reject);
    if (endpoint.kind === "tcp") server.listen(endpoint.port, endpoint.host, onListening);
    else server.listen(endpoint.path, onListening);
  });
  if (endpoint.kind === "unix") {
    try {
      fs.chmodSync(endpoint.path, 0o600); // only this user may drive the runtime
    } catch {
      // best effort (e.g. unsupported filesystem)
    }
  }
  server.on("error", (error) => log(`[pi-runtime] server error: ${String(error)}`));

  let closing: Promise<void> | null = null;
  return {
    socketPath,
    close() {
      closing ??= new Promise<void>((resolve) => {
        server.close(() => resolve());
        for (const socket of sockets) socket.destroy();
      }).finally(() => {
        if (endpoint.kind === "unix") fs.rmSync(endpoint.path, { force: true });
      });
      return closing;
    },
  };
}
