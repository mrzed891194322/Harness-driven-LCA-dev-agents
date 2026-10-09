import readline from "node:readline";
import type { ProtocolEvent, ProtocolRequest, ProtocolResponse } from "./types.js";

export type RequestHandler = (
  method: string,
  params: Record<string, unknown>,
) => Promise<unknown>;

export type HandoffSubmitHandler = (
  params: Record<string, unknown>,
) => Promise<unknown>;

export function emitEvent(event: string, data?: Record<string, unknown>): void {
  const payload: ProtocolEvent = { type: "event", event, data };
  process.stdout.write(JSON.stringify(payload) + "\n");
}

export function emitResponse(res: ProtocolResponse): void {
  process.stdout.write(JSON.stringify(res) + "\n");
}

export interface ProtocolLoopOptions {
  onHandoffSubmit?: HandoffSubmitHandler;
  /** Called once when stdin reaches EOF (the host closed the pipe or exited). */
  onClose?: () => void;
  input?: NodeJS.ReadableStream;
}

export function startProtocolLoop(
  onRequest: RequestHandler,
  options: ProtocolLoopOptions = {},
): void {
  const { onHandoffSubmit, onClose } = options;
  const rl = readline.createInterface({
    input: options.input ?? process.stdin,
    crlfDelay: Infinity,
  });
  rl.on("close", () => onClose?.());
  rl.on("line", (line) => {
    void (async () => {
      let parsed: ProtocolRequest;
      try {
        parsed = JSON.parse(line) as ProtocolRequest;
      } catch {
        return;
      }
      if (parsed.type !== "req" || !parsed.id || !parsed.method) {
        return;
      }
      const params = (parsed.params ?? {}) as Record<string, unknown>;
      try {
        let result: unknown;
        if (parsed.method === "handoff.submit" && onHandoffSubmit) {
          result = await onHandoffSubmit(params);
        } else {
          result = await onRequest(parsed.method, params);
        }
        emitResponse({ type: "res", id: parsed.id, ok: true, result });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        emitResponse({
          type: "res",
          id: parsed.id,
          ok: false,
          error: { code: "runtime_error", message },
        });
      }
    })();
  });
}
