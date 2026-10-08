#!/usr/bin/env node
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

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

run("uv", ["run", "uvicorn", "api.app:app", "--app-dir", "src", "--host", "127.0.0.1", "--port", "8000"]);
run("pnpm", ["--filter", "@harness/web", "dev"], { env: { PORT: "3000" } });

process.on("SIGINT", () => {
  for (const child of children) child.kill("SIGTERM");
  process.exit(0);
});
