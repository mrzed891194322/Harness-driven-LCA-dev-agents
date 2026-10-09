/** Indent-based YAML subset used by the harness workflow files. */

type Line = { indent: number; content: string };

export type WorkflowGraph = {
  file: string;
  id: string;
  maxAttempts: number;
  defaults: { rules: string[]; knowledge: string[] };
  rules: { id: string; path: string }[];
  mcp: McpTool[];
  hostActions: HostAction[];
  knowledge: KnowledgeSource[];
  stages: StageNode[];
  assignments: AssignmentNode[];
};

export type McpTool = {
  id: string;
  transport: string;
  command: string;
  args: string[];
  rules: string[];
  toolTimeoutSec: number | null;
  runtime: Record<string, unknown>;
};

export type HostAction = {
  id: string;
  command: string;
  args: string[];
  timeoutSec: number | null;
};

export type KnowledgeSource = {
  id: string;
  kind: string;
  path: string;
  provider: string;
};

export type StageNode = {
  id: string;
  spec: string;
  maxAttempts: number;
  rules: string[];
  phase: string;
  steps: { assignment: string }[];
};

export type AssignmentNode = {
  id: string;
  role: string;
  mcp: string[];
  rules: string[];
};

export type SpecSummary = {
  inputs: { path: string; required: boolean }[];
  outputs: { path: string; required: boolean; kind: string }[];
  checks: { id: string; action: string }[];
  afterPass: { id: string; action: string }[];
};

function tokenize(text: string): Line[] {
  const lines: Line[] = [];
  for (const raw of text.split(/\r?\n/)) {
    if (!raw.trim() || /^\s*#/.test(raw)) continue;
    const indent = raw.match(/^ */)?.[0].length ?? 0;
    lines.push({ indent, content: raw.slice(indent) });
  }
  return lines;
}

function parseScalar(value: string): unknown {
  if (value === "[]") return [];
  if (value === "{}") return {};
  if (value === "true") return true;
  if (value === "false") return false;
  if (value === "null" || value === "~") return null;
  if (/^-?\d+$/.test(value)) return Number(value);
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function splitKey(content: string): [string, string] {
  const colon = content.indexOf(":");
  if (colon <= 0) throw new Error(`无法解析 YAML：${content}`);
  return [content.slice(0, colon).trim(), content.slice(colon + 1).trim()];
}

function parse(lines: Line[], start: number, minIndent: number): { value: unknown; next: number } {
  if (start >= lines.length || lines[start].indent < minIndent) return { value: null, next: start };
  if (lines[start].content.startsWith("- ")) return parseList(lines, start);
  return parseMap(lines, start, lines[start].indent);
}

function parseMap(lines: Line[], start: number, indent: number): { value: Record<string, unknown>; next: number } {
  const map: Record<string, unknown> = {};
  let index = start;
  while (index < lines.length && lines[index].indent === indent && !lines[index].content.startsWith("- ")) {
    const [key, rest] = splitKey(lines[index].content);
    index += 1;
    if (rest) {
      map[key] = parseScalar(rest);
      continue;
    }
    const next = lines[index];
    if (next && next.content.startsWith("- ") && next.indent >= indent) {
      const child = parseList(lines, index);
      map[key] = child.value;
      index = child.next;
    } else if (next && next.indent > indent) {
      const child = parse(lines, index, indent + 1);
      map[key] = child.value;
      index = child.next;
    } else {
      map[key] = null;
    }
  }
  return { value: map, next: index };
}

function parseList(lines: Line[], start: number): { value: unknown[]; next: number } {
  const indent = lines[start].indent;
  const list: unknown[] = [];
  let index = start;
  while (index < lines.length && lines[index].indent === indent && lines[index].content.startsWith("- ")) {
    const rest = lines[index].content.slice(2).trim();
    index += 1;
    if (!rest) {
      const child = parse(lines, index, indent + 1);
      list.push(child.value);
      index = child.next;
      continue;
    }
    if (!rest.includes(":")) {
      list.push(parseScalar(rest));
      continue;
    }
    const [key, valueRest] = splitKey(rest);
    const item: Record<string, unknown> = {};
    if (valueRest) item[key] = parseScalar(valueRest);
    else if (index < lines.length && lines[index].indent > indent) {
      const child = parse(lines, index, indent + 1);
      item[key] = child.value;
      index = child.next;
    } else item[key] = null;
    if (index < lines.length && lines[index].indent > indent && !lines[index].content.startsWith("- ")) {
      const child = parseMap(lines, index, lines[index].indent);
      Object.assign(item, child.value);
      index = child.next;
    }
    list.push(item);
  }
  return { value: list, next: index };
}

export function parseYamlSubset(text: string): unknown {
  const lines = tokenize(text);
  if (!lines.length) return null;
  return parse(lines, 0, 0).value;
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} 格式无法识别`);
  }
  return value as Record<string, unknown>;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item));
}

function added(value: unknown): string[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return stringList((value as Record<string, unknown>).add);
}

function stringMap(value: unknown): { id: string; path: string }[] {
  const source = record(value ?? {}, "registry");
  return Object.entries(source).map(([id, path]) => ({ id, path: String(path) }));
}

export function readWorkflow(text: string, file: string): WorkflowGraph {
  const raw = record(parseYamlSubset(text), file);
  const registry = record(raw.registry, `${file} registry`);
  const tools = record(registry.tools, `${file} tools`);
  const mcpRaw = record(tools.mcp ?? {}, "mcp");
  const hostRaw = record(tools.host_action ?? {}, "host_action");
  const knowledgeRaw = record(registry.knowledge ?? {}, "knowledge");
  const defaults = record(raw.defaults ?? {}, "defaults");
  const stagesRaw = Array.isArray(raw.stages) ? raw.stages : [];
  const assignmentsRaw = record(raw.assignments ?? {}, "assignments");

  const mcp: McpTool[] = Object.entries(mcpRaw).map(([id, spec]) => {
    const tool = record(spec, id);
    return {
      id,
      transport: String(tool.transport ?? ""),
      command: String(tool.command ?? ""),
      args: stringList(tool.args),
      rules: stringList(tool.rules),
      toolTimeoutSec: typeof tool.tool_timeout_sec === "number" ? tool.tool_timeout_sec : null,
      runtime: tool.runtime && typeof tool.runtime === "object" && !Array.isArray(tool.runtime)
        ? (tool.runtime as Record<string, unknown>)
        : {},
    };
  });

  const hostActions: HostAction[] = Object.entries(hostRaw).map(([id, spec]) => {
    const action = record(spec, id);
    return {
      id,
      command: String(action.command ?? ""),
      args: stringList(action.args),
      timeoutSec: typeof action.timeout_sec === "number" ? action.timeout_sec : null,
    };
  });

  const knowledge: KnowledgeSource[] = Object.entries(knowledgeRaw).map(([id, spec]) => {
    const source = record(spec, id);
    return {
      id,
      kind: String(source.kind ?? ""),
      path: String(source.path ?? ""),
      provider: String(source.provider ?? ""),
    };
  });

  const stages: StageNode[] = stagesRaw.map((item) => {
    const stage = record(item, "stage");
    const context = stage.context && typeof stage.context === "object" && !Array.isArray(stage.context)
      ? (stage.context as Record<string, unknown>)
      : null;
    const lca = context?.lca && typeof context.lca === "object" && !Array.isArray(context.lca)
      ? (context.lca as Record<string, unknown>)
      : null;
    const stepsRaw = Array.isArray(stage.steps) ? stage.steps : [];
    return {
      id: String(stage.id ?? ""),
      spec: String(stage.spec ?? ""),
      maxAttempts: typeof stage.max_attempts === "number" ? stage.max_attempts : 0,
      rules: added(stage.rules),
      phase: typeof lca?.phase === "string" ? lca.phase : "",
      steps: stepsRaw.map((step) => {
        const row = record(step, "step");
        return { assignment: String(row.assignment ?? "") };
      }),
    };
  });

  const assignments: AssignmentNode[] = Object.entries(assignmentsRaw).map(([id, spec]) => {
    const assignment = record(spec, id);
    const assignmentTools = record(assignment.tools ?? {}, `${id} tools`);
    return {
      id,
      role: String(assignment.role ?? ""),
      mcp: stringList(assignmentTools.mcp),
      rules: added(assignment.rules),
    };
  });

  return {
    file,
    id: String(raw.id ?? ""),
    maxAttempts: typeof raw.max_attempts === "number" ? raw.max_attempts : 0,
    defaults: {
      rules: stringList(defaults.rules),
      knowledge: stringList(defaults.knowledge),
    },
    rules: stringMap(registry.rules),
    mcp,
    hostActions,
    knowledge,
    stages,
    assignments,
  };
}

function refList(value: unknown): { path: string; required: boolean; kind: string }[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const row = record(item, "spec ref");
    return {
      path: String(row.path ?? ""),
      required: row.required !== false,
      kind: String(row.kind ?? ""),
    };
  });
}

function actionList(value: unknown): { id: string; action: string }[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const row = record(item, "spec action");
    return { id: String(row.id ?? ""), action: String(row.action ?? "") };
  });
}

export function readSpec(text: string): SpecSummary {
  const raw = record(parseYamlSubset(text), "spec");
  const acceptance = raw.acceptance && typeof raw.acceptance === "object" && !Array.isArray(raw.acceptance)
    ? (raw.acceptance as Record<string, unknown>)
    : {};
  const lifecycle = raw.lifecycle && typeof raw.lifecycle === "object" && !Array.isArray(raw.lifecycle)
    ? (raw.lifecycle as Record<string, unknown>)
    : {};
  return {
    inputs: refList(raw.inputs).map(({ path, required }) => ({ path, required })),
    outputs: refList(raw.outputs),
    checks: actionList(acceptance.checks),
    afterPass: actionList(lifecycle.on_reviewer_passed),
  };
}
