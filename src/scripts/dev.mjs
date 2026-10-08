#!/usr/bin/env node
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function parseEnvFile(filePath) {
  const parsed = {};
  if (!fs.existsSync(filePath)) return parsed;
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const eq = line.indexOf("=");
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    parsed[key] = value;
  }
  return parsed;
}

function resolvePort(fileEnv, key, fallback) {
  const raw = (process.env[key] || fileEnv[key] || fallback).trim();
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    console.error(`${key} 不是有效端口：${raw}`);
    process.exit(1);
  }
  return port;
}

function portFree(port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", (err) => {
      if (err.code === "EADDRINUSE") resolve(false);
      else reject(err);
    });
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(port, "127.0.0.1");
  });
}

const fileEnv = parseEnvFile(path.join(root, ".env"));
const webPort = resolvePort(fileEnv, "GUI_WEB_PORT", "3000");
const apiPort = resolvePort(fileEnv, "GUI_API_PORT", "8800");

if (webPort === apiPort) {
  console.error("GUI_WEB_PORT 与 GUI_API_PORT 不能相同");
  process.exit(1);
}

const children = [];
let shuttingDown = false;

function run(cmd, args, opts = {}) {
  const child = spawn(cmd, args, {
    cwd: opts.cwd || root,
    stdio: "inherit",
    env: { ...process.env, ...opts.env },
  });
  children.push(child);
  child.on("exit", (code, signal) => {
    if (shuttingDown || signal) return;
    if (code && code !== 0) shutdown(code);
  });
  return child;
}

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) child.kill("SIGTERM");
  }
  setTimeout(() => process.exit(code), 300);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

const pythonPath = [
  path.join(root, "src", "backend"),
  path.join(root, "src", "shared"),
  path.join(root, "src"),
  root,
  process.env.PYTHONPATH || "",
]
  .filter(Boolean)
  .join(path.delimiter);

if (!(await portFree(apiPort))) {
  console.error(`后端端口 ${apiPort} 已被占用。请修改 .env 的 GUI_API_PORT。`);
  process.exit(1);
}
if (!(await portFree(webPort))) {
  console.error(`前端端口 ${webPort} 已被占用。请修改 .env 的 GUI_WEB_PORT，或先停掉已有的 npm run dev。`);
  process.exit(1);
}

console.log(`启动控制面板：前端 http://127.0.0.1:${webPort}  后端 http://127.0.0.1:${apiPort}`);

const sharedEnv = {
  GUI_WEB_PORT: String(webPort),
  GUI_API_PORT: String(apiPort),
  PYTHONPATH: pythonPath,
};

run("uv", ["run", "uvicorn", "api.app:app", "--app-dir", "src/backend", "--host", "127.0.0.1", "--port", String(apiPort)], {
  env: { ...sharedEnv, PI_RUNTIME_MOCK: process.env.PI_RUNTIME_MOCK || "1" },
});
run("npm", ["run", "dev", "-w", "@harness/web"], {
  env: { ...sharedEnv, PORT: String(webPort) },
});
