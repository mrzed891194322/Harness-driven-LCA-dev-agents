import { uiLang } from "./run-status";
import { translate } from "./i18n/messages";

const KEYS: Record<string, string> = {
  idle: "label.idle",
  running: "label.running",
  pending: "label.pending",
  completed: "label.completed",
  passed: "label.passed",
  failed: "label.failed",
  stopped: "label.stopped",
  error: "label.error",
  blocked: "label.blocked",
  ok: "label.ok",
  pass: "label.pass",
  accept: "label.accept",
  fail: "label.fail",
  reject: "label.reject",
  interrupted: "label.interrupted",
  aborted: "label.aborted",
};

export function label(value: string | undefined | null): string {
  if (!value) return "";
  const key = KEYS[value];
  if (!key) return value;
  return translate(uiLang(), key);
}

/** @deprecated use label(); kept for call sites expecting the map */
export const LABEL: Record<string, string> = Object.fromEntries(
  Object.keys(KEYS).map((k) => [k, label(k)]),
);
