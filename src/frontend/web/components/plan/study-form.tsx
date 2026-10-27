"use client";

import { useLocale } from "../../lib/i18n/locale-context";
import { useEffect, useRef, useState } from "react";
import { Eraser } from "lucide-react";
import { apiFetch } from "../../lib/api";
import {
  emptyPlanFields,
  filterValidItems,
  isSpecialItem,
  itemContent,
  itemTitle,
  normalizePlanFields,
  type PlanFields,
  type PlanItem,
  SPECIAL_TITLES,
} from "./plan-fields";

export type { PlanFields };
export type PlanTemplateSection = { id: string; required?: boolean };

const LCIA_METHODS = [
  "ReCiPe 2016 Midpoint (H)",
  "ReCiPe 2016 Endpoint (H)",
  "EF 3.1",
  "CML-IA baseline",
  "IPCC 2021",
  "TRACI 2.1",
];

export type WorkRow = {
  id: string;
  label: string;
  value: string;
  required: boolean;
  gaps: string[];
};

export type StudyWork = {
  rows: WorkRow[];
  plan: PlanFields;
};

function visibleItems(items: PlanItem[]): { item: PlanItem; index: number }[] {
  return items
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => !isSpecialItem(item) || item.enable);
}

function buildWork(plan: PlanFields, databaseLabel: string): StudyWork {
  const legalPlan: PlanFields = { ...plan, items: filterValidItems(plan.items) };
  const rows = visibleItems(legalPlan.items).map(({ item, index }, order) => {
    const label = `${order + 1} ${itemTitle(item)}`;
    let value = itemContent(item);
    if (isSpecialItem(item) && item.type === "database") {
      value = databaseLabel;
    }
    const empty = !value.trim();
    return {
      id: `item-${index}`,
      label,
      value,
      required: !(isSpecialItem(item) ? false : item.title.includes("特殊") || item.title.includes("环境影响")),
      gaps: empty && !(itemTitle(item).includes("特殊") || itemTitle(item).includes("环境影响")) ? [itemTitle(item)] : [],
    };
  });
  return { rows, plan: legalPlan };
}

export function emptyStudyWork(): StudyWork {
  return buildWork(emptyPlanFields(), "");
}

function scrollContainer(main: HTMLElement) {
  if (main.scrollHeight > main.clientHeight + 1) return main;
  const parent = main.parentElement;
  if (parent && parent.scrollHeight > parent.clientHeight + 1) return parent;
  return main;
}

export function StudyForm({
  source,
  sourceKey,
  onWork,
  templateId,
}: {
  source: PlanFields;
  sourceKey: number;
  onWork?: (work: StudyWork) => void;
  /** Kept for parent wiring; items come from uploaded / saved plan. */
  templateId?: string;
  templateSections?: PlanTemplateSection[];
}) {
  const { t } = useLocale();
  const sourceRef = useRef(source);
  sourceRef.current = source;
  const mainRef = useRef<HTMLDivElement>(null);
  const [plan, setPlan] = useState<PlanFields>(() => normalizePlanFields(source));
  const [openlcaOk, setOpenlcaOk] = useState<boolean | null>(null);
  const [databaseName, setDatabaseName] = useState("");
  const [checking, setChecking] = useState(false);
  const [activeId, setActiveId] = useState("item-0");
  const onWorkRef = useRef(onWork);
  onWorkRef.current = onWork;
  const lastWorkJson = useRef("");

  useEffect(() => {
    setPlan(normalizePlanFields(sourceRef.current, templateId));
  }, [sourceKey]);

  useEffect(() => {
    if (!templateId) return;
    setPlan((prev) => (prev.template_id === templateId ? prev : { ...prev, template_id: templateId }));
  }, [templateId]);

  useEffect(() => {
    void refreshOpenLca();
  }, []);

  const shown = visibleItems(plan.items);

  useEffect(() => {
    const root = mainRef.current;
    if (!root) return;
    const update = () => {
      const scroller = scrollContainer(root);
      const origin = scroller.getBoundingClientRect().top;
      let current = shown[0] ? `item-${shown[0].index}` : "item-0";
      for (const { index } of shown) {
        const element = document.getElementById(`item-${index}`);
        if (element && element.getBoundingClientRect().top - origin <= 48) current = `item-${index}`;
      }
      setActiveId(current);
    };
    update();
    const scroller = scrollContainer(root);
    scroller.addEventListener("scroll", update, { passive: true });
    return () => scroller.removeEventListener("scroll", update);
  }, [shown]);

  async function refreshOpenLca() {
    setChecking(true);
    try {
      const response = await apiFetch("/api/diagnostics/environment");
      const data = (await response.json()) as { openlca?: { ok?: boolean; database?: string } };
      const connected = Boolean(response.ok && data.openlca?.ok);
      setOpenlcaOk(connected);
      setDatabaseName(connected && typeof data.openlca?.database === "string" ? data.openlca.database : "");
    } catch {
      setOpenlcaOk(false);
      setDatabaseName("");
    } finally {
      setChecking(false);
    }
  }

  function patchItem(index: number, partial: Partial<PlanItem>) {
    setPlan((prev) => {
      const items = prev.items.map((item, i) => {
        if (i !== index) return item;
        if (isSpecialItem(item)) {
          return { ...item, ...partial, type: item.type } as PlanItem;
        }
        return { ...item, ...partial, title: (partial as PlanTextPatch).title ?? item.title } as PlanItem;
      });
      return { ...prev, items };
    });
  }

  type PlanTextPatch = { title?: string; content?: string };

  function clearPlan() {
    setPlan((prev) => ({
      ...prev,
      items: prev.items.map((item) => {
        if (isSpecialItem(item)) {
          return item.type === "lcia" ? { ...item, content: "" } : { ...item };
        }
        return { ...item, content: "" };
      }),
    }));
  }

  function jumpTo(id: string) {
    const root = mainRef.current;
    const target = document.getElementById(id);
    if (!root || !target) return;
    setActiveId(id);
    const scroller = scrollContainer(root);
    const top = scroller.scrollTop + target.getBoundingClientRect().top - scroller.getBoundingClientRect().top - 8;
    scroller.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }

  const databaseLabel =
    databaseName ||
    (openlcaOk ? t("study.dbConnectedNoName") : openlcaOk === false ? t("study.disconnected") : t("study.reading"));

  useEffect(() => {
    // Persist live database name into the special item content for save/preview.
    const nextItems = plan.items.map((item) => {
      if (isSpecialItem(item) && item.type === "database" && item.enable) {
        return { ...item, content: databaseName };
      }
      return item;
    });
    const nextPlan = { ...plan, template_id: templateId || plan.template_id, items: nextItems };
    const work = buildWork(nextPlan, databaseLabel);
    const json = JSON.stringify(work);
    if (json === lastWorkJson.current) return;
    lastWorkJson.current = json;
    onWorkRef.current?.(work);
  }, [plan, databaseLabel, databaseName, templateId]);

  return (
    <div className="plan-study">
      <div className="plan-study-main" ref={mainRef}>
        {shown.map(({ item, index }, order) => {
          const id = `item-${index}`;
          const title = itemTitle(item);
          if (isSpecialItem(item) && item.type === "database") {
            return (
              <section className="study-block" id={id} key={id}>
                <div className="study-block-head">
                  <h3>
                    <span className="study-num">{order + 1}</span>
                    {title}
                  </h3>
                  <span className={`study-link${openlcaOk ? " on" : ""}`}>
                    {checking ? t("study.checking") : openlcaOk ? t("study.olcaOk") : t("study.olcaDown")}
                    <button type="button" onClick={() => void refreshOpenLca()} disabled={checking}>
                      {t("study.refresh")}
                    </button>
                  </span>
                </div>
                <p>{t("study.dbChangeHint")}</p>
                <input
                  className="study-locked"
                  type="text"
                  readOnly
                  aria-readonly="true"
                  aria-label={title}
                  value={databaseLabel}
                />
              </section>
            );
          }
          if (isSpecialItem(item) && item.type === "lcia") {
            return (
              <section className="study-block" id={id} key={id}>
                <div className="study-block-head">
                  <h3>
                    <span className="study-num">{order + 1}</span>
                    {title || SPECIAL_TITLES.lcia}
                  </h3>
                  <span className={`study-link${openlcaOk ? " on" : ""}`}>
                    {checking ? t("study.checking") : openlcaOk ? t("study.olcaOk") : t("study.olcaDown")}
                    <button type="button" onClick={() => void refreshOpenLca()} disabled={checking}>
                      {t("study.refresh")}
                    </button>
                  </span>
                </div>
                <p>{t("study.lciaHelp")}</p>
                <select
                  aria-label={t("study.method")}
                  value={item.content || ""}
                  onChange={(event) => patchItem(index, { content: event.target.value })}
                >
                  <option value="">{t("study.pickMethod")}</option>
                  {LCIA_METHODS.map((method) => (
                    <option key={method} value={method}>
                      {method}
                    </option>
                  ))}
                </select>
              </section>
            );
          }
          return (
            <section className="study-block" id={id} key={id}>
              <h3>
                <span className="study-num">{order + 1}</span>
                {title}
              </h3>
              <input
                className="study-area study-line"
                type="text"
                value={itemContent(item)}
                aria-label={title}
                onChange={(event) => patchItem(index, { content: event.target.value })}
              />
            </section>
          );
        })}
      </div>

      <aside className="plan-study-side">
        <nav className="study-preview" aria-label={t("study.settings")}>
          <div className="study-preview-head">
            <h3>{t("study.previewTitle")}</h3>
            <button type="button" className="study-clear" onClick={clearPlan}>
              <Eraser size={14} aria-hidden="true" />
              {t("study.clear")}
            </button>
          </div>
          <p>{t("study.previewHelp")}</p>
          <ol className="study-nav">
            {shown.map(({ item, index }, order) => {
              const id = `item-${index}`;
              let summary = itemContent(item);
              if (isSpecialItem(item) && item.type === "database") summary = databaseLabel;
              return (
                <li key={id}>
                  <button
                    type="button"
                    aria-current={activeId === id ? "true" : undefined}
                    title={summary || undefined}
                    onClick={() => jumpTo(id)}
                  >
                    <strong>
                      <span className="study-num">{order + 1}</span>
                      {itemTitle(item)}
                    </strong>
                    <span className={summary ? undefined : "is-empty"}>{summary || t("study.unfilled")}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>
      </aside>
    </div>
  );
}
