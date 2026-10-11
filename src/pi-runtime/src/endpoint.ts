/**
 * Where the single pi-runtime listens.
 *
 * A filesystem path is a Unix domain socket (Linux / macOS).
 * `tcp://127.0.0.1:<port>` is loopback TCP, used on native Windows.
 * Any other host is rejected.
 */
import fs from "node:fs";
import path from "node:path";
import type { NetConnectOpts } from "node:net";

export const ENDPOINT_FILENAME = "pi-runtime.endpoint";

export interface TcpListenEndpoint {
  kind: "tcp";
  host: "127.0.0.1";
  port: number;
  raw: string;
}

export interface UnixListenEndpoint {
  kind: "unix";
  path: string;
  raw: string;
}

export type ListenEndpoint = TcpListenEndpoint | UnixListenEndpoint;

const TCP_LOOPBACK = /^tcp:\/\/127\.0\.0\.1:(\d+)$/;

export function parseListenEndpoint(value: string): ListenEndpoint {
  const text = value.trim();
  if (text.toLowerCase().startsWith("tcp://")) {
    const match = TCP_LOOPBACK.exec(text);
    if (!match) {
      throw new Error(`pi-runtime 只接受 tcp://127.0.0.1:<端口>，收到 ${text}`);
    }
    const port = Number(match[1]);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new Error(`pi-runtime 端口无效：${text}`);
    }
    return { kind: "tcp", host: "127.0.0.1", port, raw: `tcp://127.0.0.1:${port}` };
  }
  if (!text) throw new Error("pi-runtime 监听地址为空");
  return { kind: "unix", path: text, raw: text };
}

export function connectTarget(value: string): NetConnectOpts {
  const endpoint = parseListenEndpoint(value);
  if (endpoint.kind === "tcp") return { host: endpoint.host, port: endpoint.port };
  return { path: endpoint.path };
}

/** `.local/run/pi-runtime.endpoint` under the repo that contains `pyproject.toml`. */
export function endpointRecordPath(start: string): string | null {
  let dir = path.resolve(start);
  for (let i = 0; i < 8; i++) {
    if (fs.existsSync(path.join(dir, "pyproject.toml"))) {
      return path.join(dir, ".local", "run", ENDPOINT_FILENAME);
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

/** Delete the endpoint record only when it names this listen address. */
export function removeEndpointRecord(listenAddress: string, start = process.cwd()): void {
  const file = endpointRecordPath(start);
  if (!file || !fs.existsSync(file)) return;
  let text = "";
  try {
    text = fs.readFileSync(file, "utf8").trim();
  } catch {
    return;
  }
  if (text !== listenAddress.trim()) return;
  fs.rmSync(file, { force: true });
}
