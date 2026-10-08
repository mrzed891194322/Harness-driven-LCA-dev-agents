#!/usr/bin/env node
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const children = [];

function run(cmd, args, opts = {}) {
  const child = spawn(cmd, args, {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, ...opts.env },
  });
  children.push(child);
  return child;
}

const pythonPath = [
  path.join(root, "src", "backend"),
  path.join(root, "src", "shared"),
  path.join(root, "src"),
  root,
  process.env.PYTHONPATH || "",
]
  .filter(Boolean)
  .join(path.delimiter);

run("uv", ["run", "uvicorn", "api.app:app", "--app-dir", "src/backend", "--host", "127.0.0.1", "--port", "8000"], {
  env: { PYTHONPATH: pythonPath, PI_RUNTIME_MOCK: process.env.PI_RUNTIME_MOCK || "1" },
});
run("npm", ["run", "dev", "-w", "@harness/web"], {
  env: { PORT: "3000", PYTHONPATH: pythonPath },
});

process.on("SIGINT", () => {
  for (const child of children) child.kill("SIGTERM");
  process.exit(0);
});
