import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

function apiPort(): string {
  if (process.env.GUI_API_PORT?.trim()) return process.env.GUI_API_PORT.trim();
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
  const envPath = path.join(root, ".env");
  if (!fs.existsSync(envPath)) return "8800";
  for (const rawLine of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line.startsWith("GUI_API_PORT=")) continue;
    let value = line.slice("GUI_API_PORT=".length).trim();
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
