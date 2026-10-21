/** Helpers for the read-only /harness YAML viewer. */
export type HarnessFile = {
  path: string;
  name: string;
  group: string;
  fields: Record<string, unknown> | null;
  raw: string;
  error: { message: string; line: number | null } | null;
};
export type HarnessSection = { id: string; title: string; files: HarnessFile[] };

/** Top-level fields as [key, text, multiline]. Strings stay as-is; lists of scalars join; the rest is JSON. */
export function fieldRows(fields: Record<string, unknown> | null): [string, string, boolean][] {
  if (!fields) return [];
  return Object.entries(fields).map(([key, value]) => {
    let text: string;
    if (value === null || value === undefined) text = "—";
    else if (typeof value === "string") text = value;
    else if (typeof value === "number" || typeof value === "boolean") text = String(value);
    else if (Array.isArray(value) && value.every((v) => typeof v !== "object" || v === null)) text = value.join("、");
    else text = JSON.stringify(value, null, 2);
    return [key, text, text.includes("\n")];
  });
}

/** Raw YAML split into numbered lines, with the error line flagged. */
export function rawLines(raw: string, errorLine: number | null | undefined): { n: number; text: string; bad: boolean }[] {
  const lines = raw.replace(/\n$/, "").split("\n");
  return lines.map((text, i) => ({ n: i + 1, text, bad: errorLine === i + 1 }));
}
