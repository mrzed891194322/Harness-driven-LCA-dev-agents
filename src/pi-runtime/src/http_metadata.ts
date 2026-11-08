import { AsyncLocalStorage } from "node:async_hooks";
import { channel } from "node:diagnostics_channel";
import { isIP } from "node:net";

type RecordData = Record<string, unknown>;
type Context = { emit: (record: RecordData) => void; base: RecordData };
const context = new AsyncLocalStorage<Context>();
const ORIGIN = "https://agi.tongji.edu.cn";
function route(raw: string): RecordData {
  try {
    const url = new URL(raw);
    if (url.origin === ORIGIN && url.pathname === "/v1/chat/completions")
      return { origin: ORIGIN, path: url.pathname };
  } catch { /* Never expose raw URLs. */ }
  return { origin: "[omitted]", path: "[omitted]" };
}
function send(ctx: Context, data: RecordData): void {
  try { ctx.emit({ ...ctx.base, time: new Date().toISOString(), ...data }); } catch { /* telemetry only */ }
}
// Node's supported Undici diagnostics channel; never inspect its headers or body.
channel("undici:client:sendHeaders").subscribe((message: unknown) => {
  try {
  const ctx = context.getStore();
  if (!ctx) return;
  const socket = (message as { socket?: Record<string, unknown> }).socket;
  if (!socket) return;
  const tuple: RecordData = {};
  for (const key of ["localAddress", "remoteAddress"]) {
    const value = socket[key];
    if (typeof value === "string" && isIP(value)) tuple[key] = value;
  }
  for (const key of ["localPort", "remotePort"]) {
    const value = socket[key];
    if (typeof value === "number" && Number.isInteger(value) && value > 0 && value <= 65535) tuple[key] = value;
  }
  if (Object.keys(tuple).length) send(ctx, { phase: "socket", socket: tuple });
  } catch { /* diagnostics must never break a model request */ }
});

export function observeFetch(fetchImpl: typeof fetch, emit: Context["emit"], sessionKey: string): typeof fetch {
  let attempt = 0;
  return async (input, init) => {
    const raw = typeof input === "string" || input instanceof URL ? String(input) : input.url;
    const verb = String(init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    const ctx: Context = { emit, base: {
      session: /^wf:preflight:[a-f0-9]{8}$/.test(sessionKey) ? sessionKey : "[omitted]",
      attempt: ++attempt, provider: "Tongji", model: "Qwen3.8-27B", ...route(raw),
      method: verb === "POST" ? "POST" : "[omitted]",
    }};
    return context.run(ctx, async () => {
      send(ctx, { phase: "request" });
      let response: Response;
      try { response = await fetchImpl(input, init); }
      catch (error) { send(ctx, { phase: "transport_error", status: null }); throw error; }
      try {
        const requestId = response.headers.get("x-request-id");
        send(ctx, { phase: "response", status: response.status,
          ...(requestId && /^(?:[a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$/i.test(requestId) ? { request_id: requestId } : {}),
          ...(response.url ? { final_route: route(response.url) } : {}),
        });
      } catch { send(ctx, { phase: "observation_error" }); }
      return response; // No clone/text/json/body access; no retry or timeout changes.
    });
  };
}

export function attachPreflightMetadata(runtime: { streamSimple: (...args: any[]) => any }, emit: Context["emit"], sessionKey: string): void {
  const original = runtime.streamSimple;
  const observed = observeFetch(globalThis.fetch.bind(globalThis), emit, sessionKey);
  runtime.streamSimple = function(model, messages, options) {
    if (model.provider !== "Tongji" || model.id !== "Qwen3.8-27B" || model.api !== "openai-completions" || model.baseUrl !== ORIGIN + "/v1")
      return original.call(this, model, messages, options);
    // Preserve any existing transport; observe that transport rather than replacing it.
    const transport = options?.fetch ? observeFetch(options.fetch, emit, sessionKey) : observed;
    return original.call(this, model, messages, { ...options, fetch: transport });
  };
}
