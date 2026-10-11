// Listen address shared by dev.mjs, stop.mjs and the Python client.
// A filesystem path is a Unix socket. `tcp://127.0.0.1:<port>` is loopback TCP
// (native Windows). Any other host is rejected.
import fs from "node:fs";
import net from "node:net";
import path from "node:path";

export const ENDPOINT_FILENAME = "pi-runtime.endpoint";
const TCP_LOOPBACK = /^tcp:\/\/127\.0\.0\.1:(\d+)$/;

export function parseListenEndpoint(value) {
  const text = String(value ?? "").trim();
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

export function isTcpEndpoint(value) {
  return String(value ?? "").trim().toLowerCase().startsWith("tcp://");
}

export function connectEndpoint(value) {
  const endpoint = parseListenEndpoint(value);
  if (endpoint.kind === "tcp") return net.connect(endpoint.port, endpoint.host);
  return net.connect(endpoint.path);
}

export function endpointFile(repoRoot) {
  return path.join(repoRoot, ".local", "run", ENDPOINT_FILENAME);
}

export function readEndpointFile(repoRoot) {
  try {
    const text = fs.readFileSync(endpointFile(repoRoot), "utf8").trim();
    return text;
  } catch {
    return "";
  }
}

export function writeEndpointFile(repoRoot, endpoint) {
  const file = endpointFile(repoRoot);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const parsed = parseListenEndpoint(endpoint);
  const line = parsed.kind === "tcp" ? parsed.raw : path.resolve(parsed.path);
  fs.writeFileSync(file, `${line}\n`, "utf8");
  return line;
}

/** Bind an ephemeral loopback port, skipping `reserved`. */
export function allocateLoopbackPort(reserved) {
  const avoid = reserved instanceof Set ? reserved : new Set(reserved);
  const once = () =>
    new Promise((resolve, reject) => {
      const server = net.createServer();
      server.once("error", reject);
      server.listen(0, "127.0.0.1", () => {
        const address = server.address();
        const port = address && typeof address === "object" ? address.port : 0;
        server.close((error) => (error ? reject(error) : resolve(port)));
      });
    });
  return (async () => {
    for (let attempt = 0; attempt < 30; attempt++) {
      const port = await once();
      if (port && !avoid.has(port)) return port;
    }
    throw new Error("没有可用的本机端口");
  })();
}
