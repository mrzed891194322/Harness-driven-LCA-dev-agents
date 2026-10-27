/**
 * Coerce LLM-stringified JSON arrays before tool schema validation.
 *
 * Tongji/Qwen (and similar) often send array fields as a JSON string, e.g.
 * artifacts: '["path"]' instead of ["path"]. pi-ai validateToolArguments rejects
 * that before the call reaches MCP (FastMCP pre_parse never runs). The intended
 * hook is ToolDefinition.prepareArguments — same pattern as built-in edit.edits.
 *
 * Only fields whose JSON Schema allows type "array" are coerced, and only when
 * the value is a string that JSON.parse-s to an Array. Pure string fields
 * (write/edit content) are left alone.
 */

type JsonSchema = {
  type?: string | string[];
  properties?: Record<string, JsonSchema>;
  anyOf?: JsonSchema[];
  oneOf?: JsonSchema[];
  allOf?: JsonSchema[];
  items?: JsonSchema | JsonSchema[];
};

export function schemaAllowsArray(schema: unknown): boolean {
  if (!schema || typeof schema !== "object") return false;
  const s = schema as JsonSchema;
  const types = Array.isArray(s.type) ? s.type : s.type ? [s.type] : [];
  if (types.includes("array")) return true;
  for (const key of ["anyOf", "oneOf", "allOf"] as const) {
    const alts = s[key];
    if (Array.isArray(alts) && alts.some(schemaAllowsArray)) return true;
  }
  return false;
}

/** If value is a string that parses as a JSON array, return that array; else value unchanged. */
export function tryParseJsonArray(value: unknown): unknown {
  if (typeof value !== "string") return value;
  const trimmed = value.trim();
  if (!trimmed.startsWith("[")) return value;
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    return Array.isArray(parsed) ? parsed : value;
  } catch {
    return value;
  }
}

/**
 * In-place (and returns) coercion of stringified arrays on object args, guided by
 * the tool's JSON Schema / TypeBox parameters. Non-objects are returned as-is.
 */
export function coerceStringifiedArrayArgs(args: unknown, parameters: unknown): unknown {
  if (!args || typeof args !== "object" || Array.isArray(args)) return args;
  const props = (parameters as JsonSchema | null | undefined)?.properties;
  if (!props) return args;
  const out = args as Record<string, unknown>;
  for (const [key, propSchema] of Object.entries(props)) {
    if (!(key in out)) continue;
    if (!schemaAllowsArray(propSchema)) continue;
    const next = tryParseJsonArray(out[key]);
    if (next !== out[key]) out[key] = next;
  }
  return out;
}

type ToolLike = {
  name: string;
  parameters: unknown;
  prepareArguments?: (args: unknown) => unknown;
};

type SessionLike = {
  getAllTools(): Array<{ name: string }>;
  getToolDefinition(name: string): ToolLike | undefined;
};

const FLAG = "__harnessArgCoerce";

function wrapPrepare(tool: ToolLike): boolean {
  if ((tool as Record<string, unknown>)[FLAG]) return false;
  const prior = tool.prepareArguments;
  tool.prepareArguments = (args: unknown) => {
    const base = typeof prior === "function" ? prior(args) : args;
    return coerceStringifiedArrayArgs(base, tool.parameters);
  };
  (tool as Record<string, unknown>)[FLAG] = true;
  return true;
}

/**
 * Attach prepareArguments coercion to every registered tool definition and to
 * the live AgentTool objects in the session registry (private _toolRegistry).
 * Safe to call repeatedly (e.g. after mcp_servers_change).
 */
export function installArgCoerceOnSession(session: SessionLike): number {
  let n = 0;
  for (const { name } of session.getAllTools()) {
    const def = session.getToolDefinition(name);
    if (def && wrapPrepare(def)) n += 1;
  }
  const registry = (session as { _toolRegistry?: Map<string, ToolLike> })._toolRegistry;
  if (registry) {
    for (const tool of registry.values()) {
      if (wrapPrepare(tool)) n += 1;
    }
  }
  return n;
}
