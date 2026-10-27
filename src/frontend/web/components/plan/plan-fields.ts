/** Plan document: upload-what-you-render items list. */

export type PlanTextItem = {
  title: string;
  content: string;
  type?: undefined;
  enable?: undefined;
};

export type PlanSpecialItem = {
  type: "database" | "lcia";
  enable: boolean;
  title?: string;
  content?: string;
};

export type PlanItem = PlanTextItem | PlanSpecialItem;

export type PlanFields = {
  template_id: string;
  items: PlanItem[];
};

export const SPECIAL_TITLES: Record<"database" | "lcia", string> = {
  database: "LCA 数据库",
  lcia: "LCIA 方法",
};

export function emptyPlanFields(templateId = "full-lifecycle"): PlanFields {
  return { template_id: templateId, items: defaultPlanItems() };
}

export function defaultPlanItems(): PlanItem[] {
  return [
    { title: "研究对象", content: "" },
    { title: "计算基准（功能单位）", content: "" },
    { title: "生命周期范围", content: "" },
    { title: "地域与时间", content: "" },
    { type: "database", enable: true },
    { type: "lcia", enable: true, content: "" },
    { title: "关注的环境影响", content: "" },
    { title: "特殊要求", content: "" },
  ];
}

export function isSpecialItem(item: PlanItem): item is PlanSpecialItem {
  return item.type === "database" || item.type === "lcia";
}

export function itemTitle(item: PlanItem): string {
  if (isSpecialItem(item)) {
    return (item.title || SPECIAL_TITLES[item.type]).trim() || SPECIAL_TITLES[item.type];
  }
  return item.title;
}

export function itemContent(item: PlanItem): string {
  if (isSpecialItem(item)) return item.content || "";
  return item.content;
}

/** Keep only schema-legal items; illegal fragments are dropped (never rendered / saved). */
export function filterValidItems(raw: unknown): PlanItem[] {
  if (!Array.isArray(raw)) return [];
  const out: PlanItem[] = [];
  for (const entry of raw) {
    const item = tryNormalizeItem(entry);
    if (item) out.push(item);
  }
  return out;
}

export function normalizePlanFields(raw: Partial<PlanFields> | null | undefined, fallbackId = "full-lifecycle"): PlanFields {
  const template_id = (raw?.template_id || fallbackId).trim() || fallbackId;
  const items = filterValidItems(raw?.items);
  return { template_id, items: items.length ? items : defaultPlanItems() };
}

function tryNormalizeItem(raw: unknown): PlanItem | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const type = typeof row.type === "string" ? row.type.trim().toLowerCase() : "";
  if (type === "database" || type === "lcia") {
    if (typeof row.enable !== "boolean") return null;
    if (row.content != null && typeof row.content !== "string" && typeof row.content !== "number") return null;
    return {
      type,
      enable: row.enable,
      title: typeof row.title === "string" ? row.title : undefined,
      content: row.content == null ? "" : String(row.content),
    };
  }
  if (type) return null; // unknown special type
  if (typeof row.title !== "string" || !row.title.trim()) return null;
  if (!("content" in row)) return null;
  if (row.content != null && typeof row.content !== "string" && typeof row.content !== "number") return null;
  return {
    title: row.title.trim(),
    content: row.content == null ? "" : String(row.content),
  };
}

export function missingPlanFields(fields: PlanFields): string[] {
  const gaps: string[] = [];
  for (const item of fields.items) {
    if (isSpecialItem(item)) {
      if (!item.enable) continue;
      if (item.type === "lcia" && !(item.content || "").trim()) gaps.push(itemTitle(item));
      continue;
    }
    if (!item.content.trim()) gaps.push(item.title || "未命名项");
  }
  return gaps;
}
