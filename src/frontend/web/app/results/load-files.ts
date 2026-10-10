"use server";

import fs from "node:fs";
import path from "node:path";

type Handoff = {
  name: string;
  stage: string;
  role: string;
  attempt: number | null;
  status: string;
  status_reason: string;
  artifacts: string[];
};

type Artifact = {
  path: string;
  size: number;
  count: number;
};

export type ResultFiles = {
  manifest: {
    status?: string;
    current_stage?: string | null;
    status_reason?: string | null;
    run_id?: string | null;
  };
  handoffs: Handoff[];
  artifacts: Artifact[];
};

function projectRoot(): string {
  let dir = process.cwd();
  for (let i = 0; i < 6; i += 1) {
    if (fs.existsSync(path.join(dir, "workspace")) && fs.existsSync(path.join(dir, "src"))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return dir;
}

function listHandoffs(folder: string): Handoff[] {
  if (!fs.existsSync(folder)) return [];
  return fs
    .readdirSync(folder)
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => {
      const row: Handoff = {
        name,
        stage: "",
        role: "",
        attempt: null,
        status: "",
        status_reason: "",
        artifacts: [],
      };
      try {
        const payload = JSON.parse(fs.readFileSync(path.join(folder, name), "utf8")) as Record<string, unknown>;
        row.stage = String(payload.stage || "");
        row.role = String(payload.role || "");
        row.attempt = typeof payload.attempt === "number" ? payload.attempt : null;
        row.status = String(payload.status || "");
        row.status_reason = String(payload.status_reason || "");
        if (Array.isArray(payload.artifacts)) {
          row.artifacts = payload.artifacts.filter((item): item is string => typeof item === "string");
        }
      } catch {
        row.status_reason = "无法读取";
      }
      return row;
    });
}

function listArtifacts(root: string): Artifact[] {
  if (!fs.existsSync(root)) return [];
  const items: Artifact[] = [];
  const grouped = new Map<string, Artifact>();

  function walk(dir: string) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name.startsWith(".")) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
        continue;
      }
      if (!entry.isFile() || entry.name === "README.md") continue;
      const relative = path.relative(root, full).split(path.sep);
      const size = fs.statSync(full).size;
      if (entry.name === "raw.json" && relative.length >= 6 && relative[0] === "reports" && relative[1] === "runs") {
        const key = `workspace/outputs/${relative.slice(0, 5).join("/")}`;
        const bucket = grouped.get(key) || { path: key, size: 0, count: 0 };
        bucket.size += size;
        bucket.count += 1;
        grouped.set(key, bucket);
        continue;
      }
      items.push({ path: `workspace/outputs/${relative.join("/")}`, size, count: 1 });
    }
  }

  walk(root);
  items.sort((a, b) => a.path.localeCompare(b.path));
  return items.concat([...grouped.values()].sort((a, b) => a.path.localeCompare(b.path)));
}

const RESULT_PREFIXES = ["workspace/outputs/", "workspace/records/handoffs/"];
const MAX_RESULT_BYTES = 512_000;

export type ResultFile = {
  path: string;
  kind: "markdown" | "json" | "text" | "too-large";
  size: number;
  text: string;
};

function resultRelative(relative: string): string {
  const parts = relative
    .replaceAll("\\", "/")
    .replace(/^\/+/, "")
    .split("/")
    .filter((part) => part && part !== ".");
  if (parts.some((part) => part === "..")) throw new Error("非法路径");
  const rel = parts.join("/");
  if (!RESULT_PREFIXES.some((prefix) => rel.startsWith(prefix))) {
    throw new Error("只能读取产物或交接记录");
  }
  return rel;
}

export async function readResultFile(relative: string): Promise<ResultFile> {
  const rel = resultRelative(relative);
  const full = path.resolve(projectRoot(), rel);
  const root = path.resolve(projectRoot());
  if (full !== root && !full.startsWith(root + path.sep)) throw new Error("非法路径");
  if (!fs.existsSync(full) || !fs.statSync(full).isFile()) throw new Error("文件不存在");
  const size = fs.statSync(full).size;
  if (size > MAX_RESULT_BYTES) return { path: rel, kind: "too-large", size, text: "" };
  let text = fs.readFileSync(full, "utf8");
  const lower = full.toLowerCase();
  if (lower.endsWith(".md")) return { path: rel, kind: "markdown", size, text };
  if (lower.endsWith(".json")) {
    try {
      text = JSON.stringify(JSON.parse(text), null, 2);
      return { path: rel, kind: "json", size, text };
    } catch {
      return { path: rel, kind: "text", size, text };
    }
  }
  return { path: rel, kind: "text", size, text };
}

export async function loadResultFiles(): Promise<ResultFiles> {
  const root = projectRoot();
  const workspace = path.join(root, "workspace");
  let manifest: ResultFiles["manifest"] = { status: "idle" };
  const manifestPath = path.join(workspace, "records", "manifest.json");
  if (fs.existsSync(manifestPath)) {
    try {
      manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8")) as ResultFiles["manifest"];
    } catch {
      manifest = { status: "idle", status_reason: "无法读取运行摘要" };
    }
  }
  return {
    manifest,
    handoffs: listHandoffs(path.join(workspace, "records", "handoffs")),
    artifacts: listArtifacts(path.join(workspace, "outputs")),
  };
}
