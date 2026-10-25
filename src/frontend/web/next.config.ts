import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

function apiPort(): string {
  if (process.env.GUI_API_PORT?.trim()) return process.env.GUI_API_PORT.trim();
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
  const configPath = path.join(root, "config.toml");
  if (!fs.existsSync(configPath)) return "8800";
  let section = "";
  for (const rawLine of fs.readFileSync(configPath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const sec = line.match(/^\[([A-Za-z0-9_]+)\]$/);
    if (sec) {
      section = sec[1];
      continue;
    }
    if (section !== "gui" || !line.startsWith("api_port")) continue;
    const eq = line.indexOf("=");
    if (eq < 0) continue;
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (value) return value;
  }
  return "8800";
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `http://127.0.0.1:${apiPort()}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
