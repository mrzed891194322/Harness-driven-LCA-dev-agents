export type AgentModel = { model: string; thinking: string; model_source?: string };

/** Model cell of the node-detail agent table: resolved model id, its origin, and thinking level (I-37). */
export function modelLine(a: AgentModel): string {
  const origin = a.model_source === "default" ? "（默认）" : "";
  return `${a.model}${origin} · 思考 ${a.thinking}`;
}
