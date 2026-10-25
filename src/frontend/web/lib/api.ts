import { translate } from "./i18n/messages";
import { uiLang } from "./run-status";
/**
 * fetch() wrapper for the control-panel API (ISSUES F1).
 *
 * When the backend is down, the Next.js /api proxy answers with a plain-text
 * "Internal Server Error", and `response.json()` then fails with
 * `Unexpected token 'I', "Internal S"... is not valid JSON`. apiFetch turns
 * connection failures and non-JSON 5xx answers into a readable ApiError instead.
 * JSON responses (including FastAPI 4xx/5xx with `detail`) are returned unchanged.
 */

export function backendDownMessage(): string {
  return translate(uiLang(), "api.backendDownDetail");
}

/** @deprecated use backendDownMessage() so locale is current */
export const BACKEND_DOWN_MESSAGE = "BACKEND_DOWN";

export class ApiError extends Error {
  readonly status: number;
  readonly backendDown: boolean;

  constructor(message: string, status: number, backendDown: boolean) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.backendDown = backendDown;
  }
}

function isJson(response: Response): boolean {
  return (response.headers.get("content-type") || "").toLowerCase().includes("json");
}

/** True when GET /api/health answers 200 with JSON. */
export async function backendReachable(timeoutMs = 3000): Promise<boolean> {
  try {
    const response = await fetch("/api/health", {
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    return response.ok && isJson(response);
  } catch {
    return false;
  }
}

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(backendDownMessage(), 0, true);
  }
  if (response.status >= 500 && !isJson(response)) {
    // Proxy error page or a crashed handler: tell the two apart via /api/health.
    if (!(await backendReachable())) {
      throw new ApiError(backendDownMessage(), response.status, true);
    }
    const body = (await response.text().catch(() => "")).trim().slice(0, 200);
    const suffix = body ? translate(uiLang(), "api.bodySuffix", { body }) : "";
    throw new ApiError(
      translate(uiLang(), "api.backendHttp", { status: response.status, suffix }),
      response.status,
      false,
    );
  }
  return response;
}

/** Message for a caught error; never surfaces raw JSON parse errors. */
export function errorText(reason: unknown, fallback: string): string {
  if (reason instanceof ApiError) return reason.message;
  if (reason instanceof SyntaxError) return translate(uiLang(), "api.notJson", { fallback });
  if (reason instanceof Error && reason.message) return reason.message;
  return fallback;
}
