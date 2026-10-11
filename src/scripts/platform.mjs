// Windows-only helpers kept pure so they can be tested on Linux.
import path from "node:path";

export const REPO_PROCESS_PATTERNS = [
  { kind: "pi-runtime", re: /pi-runtime[\\/](dist[\\/]main\.js|src[\\/]main\.ts)/ },
  { kind: "orchestrator", re: /src[\\/]scripts[\\/]workflow\.py/ },
  { kind: "mcp", re: /harness[\\/]tools[\\/]mcp[\\/]/ },
  { kind: "backend", re: /backend\.api\.app:app/ },
  { kind: "web", re: /node_modules[\\/]\.bin[\\/]next dev|next[\\/]dist[\\/]bin[\\/]next dev|^next-server\b/ },
];

export function matchRepoProcess(args) {
  return REPO_PROCESS_PATTERNS.find((pattern) => pattern.re.test(args))?.kind ?? null;
}

/** Windows ships bash.exe that starts another environment. Never use it. */
export function isWindowsSystemBash(file) {
  const norm = path.win32.normalize(String(file)).replaceAll("/", "\\").toLowerCase();
  return /\\windows\\(system32|sysnative|syswow64)\\bash\.exe$/.test(norm);
}

export function gitBashCandidates(env) {
  const found = [];
  if (env.ProgramFiles) found.push(path.win32.join(env.ProgramFiles, "Git", "bin", "bash.exe"));
  const x86 = env["ProgramFiles(x86)"];
  if (x86) found.push(path.win32.join(x86, "Git", "bin", "bash.exe"));
  if (env.LOCALAPPDATA) found.push(path.win32.join(env.LOCALAPPDATA, "Programs", "Git", "bin", "bash.exe"));
  return found;
}

export const BASH_MISSING_MESSAGE = [
  "请检查是否将Git for Windows安装在默认路径，或在PATH中加入bash.exe",
  "Check whether Git for Windows is installed in the default location, or add bash.exe to PATH.",
].join("\n");

function pathDirs(env, delimiter) {
  const key = Object.keys(env).find((name) => name.toLowerCase() === "path");
  return String(env[key] || "")
    .split(delimiter)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function findGitBash(env, exists, delimiter = path.delimiter) {
  const override = String(env.PI_BASH || "").trim();
  if (override) {
    if (isWindowsSystemBash(override)) return { error: BASH_MISSING_MESSAGE };
    if (!exists(override)) return { error: BASH_MISSING_MESSAGE };
    return { path: override };
  }
  for (const candidate of gitBashCandidates(env)) {
    if (exists(candidate)) return { path: candidate };
  }
  for (const dir of pathDirs(env, delimiter)) {
    const candidate = path.win32.join(dir, "bash.exe");
    if (isWindowsSystemBash(candidate) || !exists(candidate)) continue;
    return { path: candidate };
  }
  return { error: BASH_MISSING_MESSAGE };
}

export function prependPath(env, dir, delimiter = path.delimiter) {
  const key = Object.keys(env).find((name) => name.toLowerCase() === "path") ?? "PATH";
  const current = env[key] || "";
  const rest = current
    .split(delimiter)
    .filter((part) => part && path.win32.normalize(part).toLowerCase() !== path.win32.normalize(dir).toLowerCase());
  env[key] = [dir, ...rest].join(delimiter);
  return env;
}

export function parseWin32ProcessList(stdout, repoRoot, selfPid = 0) {
  const text = String(stdout ?? "").trim();
  if (!text) return [];
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    return [];
  }
  const rows = Array.isArray(parsed) ? parsed : [parsed];
  const needle = path.win32.normalize(repoRoot).replaceAll("/", "\\").toLowerCase();
  const found = [];
  for (const row of rows) {
    const pid = Number(row?.ProcessId);
    const args = String(row?.CommandLine ?? "");
    if (!Number.isInteger(pid) || pid <= 0 || pid === selfPid || !args) continue;
    const folded = args.replaceAll("/", "\\").toLowerCase();
    if (!folded.includes(needle)) continue;
    const kind = matchRepoProcess(args);
    if (kind) found.push({ pid, kind, args });
  }
  return found;
}
