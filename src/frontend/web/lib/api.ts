/**
 * fetch() wrapper for the control-panel API (ISSUES F1).
 *
 * When the backend is down, the Next.js /api proxy answers with a plain-text
 * "Internal Server Error", and `response.json()` then fails with
 * `Unexpected token 'I', "Internal S"... is not valid JSON`. apiFetch turns
 * connection failures and non-JSON 5xx answers into a readable ApiError instead.
 * JSON responses (including FastAPI 4xx/5xx with `detail`) are returned unchanged.
 */

export const BACKEND_DOWN_MESSAGE =
  "后端未连接：无法访问控制面板后端。请确认后端已启动（npm run dev），或查看 .local/logs/backend.log。";

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
    throw new ApiError(BACKEND_DOWN_MESSAGE, 0, true);
  }
  if (response.status >= 500 && !isJson(response)) {
    // Proxy error page or a crashed handler: tell the two apart via /api/health.
    if (!(await backendReachable())) {
      throw new ApiError(BACKEND_DOWN_MESSAGE, response.status, true);
    }
    const body = (await response.text().catch(() => "")).trim().slice(0, 200);
    throw new ApiError(
      `后端错误（HTTP ${response.status}）${body ? `：${body}` : ""}。详情见 .local/logs/backend.log。`,
      response.status,
      false,
    );
  }
  return response;
}

/** Message for a caught error; never surfaces raw JSON parse errors. */
export function errorText(reason: unknown, fallback: string): string {
  if (reason instanceof ApiError) return reason.message;
  if (reason instanceof SyntaxError) return `${fallback}（后端返回的不是 JSON）`;
  if (reason instanceof Error && reason.message) return reason.message;
  return fallback;
}
