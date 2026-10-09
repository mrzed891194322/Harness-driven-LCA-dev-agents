// Minimal stdio MCP server for runtime tests: one tool, records its pid.
import fs from "node:fs";
import readline from "node:readline";

const pidFile = process.argv[2];
if (pidFile) fs.writeFileSync(pidFile, String(process.pid));

const send = (msg) => process.stdout.write(JSON.stringify({ jsonrpc: "2.0", ...msg }) + "\n");
const rl = readline.createInterface({ input: process.stdin });
rl.on("line", (line) => {
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    return;
  }
  if (msg.id === undefined) return; // notification
  switch (msg.method) {
    case "initialize":
      send({
        id: msg.id,
        result: {
          protocolVersion: msg.params?.protocolVersion ?? "2025-06-18",
          capabilities: { tools: {} },
          serverInfo: { name: "fake", version: "1.0.0" },
        },
      });
      break;
    case "tools/list":
      send({
        id: msg.id,
        result: {
          tools: [{ name: "ping", description: "ping", inputSchema: { type: "object", properties: {} } }],
        },
      });
      break;
    case "ping":
      send({ id: msg.id, result: {} });
      break;
    default:
      send({ id: msg.id, error: { code: -32601, message: `unknown method ${msg.method}` } });
  }
});
rl.on("close", () => process.exit(0));
