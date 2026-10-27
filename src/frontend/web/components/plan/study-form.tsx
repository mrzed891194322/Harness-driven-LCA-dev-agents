"use client";

import { useLocale } from "../../lib/i18n/locale-context";
import { translate } from "../../lib/i18n/messages";
import { uiLang } from "../../lib/run-status";
import { useEffect, useRef, useState } from "react";
import {
  Eraser,
  Factory,
  Leaf,
  Plus,
  Recycle,
  Truck,
  Trash2,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { apiFetch } from "../../lib/api";

export type PlanTemplateSection = { id: string; required?: boolean };

export type PlanFields = {
  subject: string;
  functional_unit: string;
  life_cycle_stages: string;
  conditions: string;
};

type StageId = "raw" | "make" | "ship" | "use" | "end";
type ImpactScope = "all" | "selected";

type StudyObject = { id: string; name: string };

type StudyDraft = {
  objects: StudyObject[];
  quantity: string;
  unit: string;
  functionalSpec: string;
  stages: Record<StageId, boolean>;
  scopeNote: string;
  place: string;
  lcia: string;
  impactScope: ImpactScope;
  impactNote: string;
  special: string;
};

const UNITS = ["瓶", "个", "kg", "t", "m³", "kWh", "MJ", "p", "Item(s)"];
const CUSTOM_UNIT = "__custom__";

const LCIA_METHODS = [
  "ReCiPe 2016 Midpoint (H)",
  "ReCiPe 2016 Endpoint (H)",
  "EF 3.1",
  "CML-IA baseline",
  "IPCC 2021",
  "TRACI 2.1",
];

const STAGES: { id: StageId; label: string; labelKey: string; icon: LucideIcon }[] = [
  { id: "raw", label: "原材料获取", labelKey: "study.stageRaw", icon: Leaf },
  { id: "make", label: "制造", labelKey: "study.stageMake", icon: Factory },
  { id: "ship", label: "配送", labelKey: "study.stageDeliver", icon: Truck },
  { id: "use", label: "使用", labelKey: "study.stageUse", icon: UserRound },
  { id: "end", label: "最终处置", labelKey: "study.stageDispose", icon: Recycle },
];

const STUDY_SECTIONS = [
  { id: "study-sec-subject", num: "1", titleKey: "study.subject" },
  { id: "study-sec-basis", num: "2", titleKey: "study.fu" },
  { id: "study-sec-life", num: "3", titleKey: "study.scope" },
  { id: "study-sec-place", num: "4", titleKey: "study.geoTime" },
  { id: "study-sec-database", num: "5", titleKey: "study.db" },
  { id: "study-sec-lcia", num: "6", titleKey: "study.lcia" },
  { id: "study-sec-impact", num: "7", titleKey: "study.impacts" },
  { id: "study-sec-special", num: "8", titleKey: "study.special" },
] as const;

function emptyStages(): Record<StageId, boolean> {
  return { raw: false, make: false, ship: false, use: false, end: false };
}

function blankDraft(): StudyDraft {
  return {
    objects: [{ id: "object-1", name: "" }],
    quantity: "",
    unit: "",
    functionalSpec: "",
    stages: emptyStages(),
    scopeNote: "",
    place: "",
    lcia: "",
    impactScope: "all",
    impactNote: "",
    special: "",
  };
}

const LABEL = /^\s*(?:[-*]\s*)?([^：:\n]{1,12})[：:]\s*(.*)$/;

function stageIdsFrom(text: string): StageId[] {
  return STAGES.filter((stage) => text.includes(stage.label)).map((stage) => stage.id);
}

/** Restore the structured form from the saved four-field plan (also accepts v1 free text).
 *
 * Template import puts sections 2 and 3 entirely under 附加说明. Lines after that
 * label stay in the note, so quantity, unit, and stage names are not applied to
 * the selectable controls. The form's own save still writes those labels first.
 */
function hydrate(fields: PlanFields): StudyDraft {
  const filled = [fields.subject, fields.functional_unit, fields.life_cycle_stages, fields.conditions].some((item) =>
    item.trim(),
  );
  if (!filled) return blankDraft();
  const draft = blankDraft();

  const objects = fields.subject
    .split(/\n\s*\n/)
    .map((item) => item.trim())
    .filter(Boolean);
  draft.objects = (objects.length ? objects : [""]).map((name, index) => ({ id: `object-${index + 1}`, name }));
  objectSeq = Math.max(objectSeq, draft.objects.length);

  const fuNotes: string[] = [];
  let fuNote = false;
  for (const line of fields.functional_unit.split("\n")) {
    if (fuNote) {
      fuNotes.push(line);
      continue;
    }
    const match = LABEL.exec(line);
    const key = match?.[1].trim();
    if (match && key === translate(uiLang(), "study.qty") && !draft.quantity) draft.quantity = match[2].trim();
    else if (match && key === translate(uiLang(), "study.unit") && !draft.unit) draft.unit = match[2].trim();
    else if (match && key === translate(uiLang(), "study.extra")) {
      fuNote = true;
      if (match[2].trim()) fuNotes.push(match[2].trim());
    } else {
      fuNote = true;
      fuNotes.push(line);
    }
  }
  draft.functionalSpec = fuNotes.join("\n").trim();

  const scopeNotes: string[] = [];
  let stagesFound = false;
  let scopeNote = false;
  for (const line of fields.life_cycle_stages.split("\n")) {
    if (scopeNote) {
      scopeNotes.push(line);
      continue;
    }
    const match = LABEL.exec(line);
    const key = match?.[1].trim();
    if (!stagesFound && match && (key === translate(uiLang(), "study.stage") || key === translate(uiLang(), "study.stages")) && stageIdsFrom(match[2]).length) {
      for (const id of stageIdsFrom(match[2])) draft.stages[id] = true;
      stagesFound = true;
    } else if (match && key === translate(uiLang(), "study.extra")) {
      scopeNote = true;
      if (match[2].trim()) scopeNotes.push(match[2].trim());
    } else {
      scopeNote = true;
      scopeNotes.push(line);
    }
  }
  draft.scopeNote = scopeNotes.join("\n").trim();

  const special: string[] = [];
  for (const block of fields.conditions.split(/\n\s*\n/)) {
    const text = block.trim();
    if (!text) continue;
    if (/^地域与时间[：:]/.test(text)) {
      draft.place = text.replace(/^地域与时间[：:]\s*/, "").trim();
      continue;
    }
    const match = text.includes("\n") ? null : LABEL.exec(text);
    const key = match?.[1].trim();
    if (match && key === translate(uiLang(), "study.db")) continue;
    else if (match && key === translate(uiLang(), "study.method") && !draft.lcia) draft.lcia = match[2].trim();
    else if (text === translate(uiLang(), "study.allIndicators")) draft.impactScope = "all";
    else if (text.startsWith(translate(uiLang(), "study.onlyIndicators"))) {
      draft.impactScope = "selected";
      draft.impactNote = text.replace(/^仅指定指标[：:]?\s*/, "").trim();
    } else special.push(text);
  }
  draft.special = special.join("\n\n");
  return draft;
}

function filledLines(lines: Array<string | false>) {
  return lines.filter((line): line is string => Boolean(line)).join("\n");
}

function sectionSummaries(draft: StudyDraft, database: string) {
  const objects = draft.objects.map((item) => item.name.trim()).filter(Boolean);
  const stages = STAGES.filter((stage) => draft.stages[stage.id]).map((stage) => stage.label);
  return {
    "study-sec-subject": objects.join("\n\n"),
    "study-sec-basis": filledLines([
      draft.quantity.trim() && `数量：${draft.quantity.trim()}`,
      draft.unit.trim() && `单位：${draft.unit.trim()}`,
      draft.functionalSpec.trim() && `附加说明：${draft.functionalSpec.trim()}`,
    ]),
    "study-sec-life": filledLines([
      stages.length > 0 && stages.join(" → "),
      draft.scopeNote.trim() && `附加说明：${draft.scopeNote.trim()}`,
    ]),
    "study-sec-place": draft.place.trim(),
    "study-sec-database": database.trim(),
    "study-sec-lcia": draft.lcia.trim(),
    "study-sec-impact":
      draft.impactScope === "selected"
        ? filledLines([translate(uiLang(), "study.onlyIndicators"), draft.impactNote.trim() && draft.impactNote.trim()])
        : translate(uiLang(), "study.allIndicators"),
    "study-sec-special": draft.special.trim(),
  };
}

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

function gapList(draft: StudyDraft, databaseName: string): Record<(typeof STUDY_SECTIONS)[number]["id"], string[]> {
  const stagePicked = STAGES.some((stage) => draft.stages[stage.id]);
  const objects = draft.objects.map((item) => item.name.trim());
  return {
    "study-sec-subject": objects.length > 0 && objects.every(Boolean) ? [] : [translate(uiLang(), "study.subject")],
    "study-sec-basis": [draft.quantity.trim() ? "" : translate(uiLang(), "study.qty"), draft.unit.trim() ? "" : translate(uiLang(), "study.unit")].filter(Boolean),
    "study-sec-life": stagePicked ? [] : [translate(uiLang(), "study.stages")],
    "study-sec-place": draft.place.trim() ? [] : [translate(uiLang(), "study.geoTime")],
    "study-sec-database": databaseName.trim() ? [] : [translate(uiLang(), "study.db")],
    "study-sec-lcia": draft.lcia.trim() ? [] : [translate(uiLang(), "study.method")],
    "study-sec-impact": draft.impactScope === "selected" && !draft.impactNote.trim() ? [translate(uiLang(), "study.specifyIndicators")] : [],
    "study-sec-special": [],
  };
}

export function studyWork(draft: StudyDraft, databaseLabel: string, databaseName: string): StudyWork {
  const summaries = sectionSummaries(draft, databaseLabel);
  const gaps = gapList(draft, databaseName);
  const stages = STAGES.filter((stage) => draft.stages[stage.id]).map((stage) => stage.label);
  const impact =
    draft.impactScope === "selected"
      ? [translate(uiLang(), "study.onlyIndicators"), draft.impactNote.trim()].filter(Boolean).join("：")
      : translate(uiLang(), "study.allIndicators");
  return {
    rows: STUDY_SECTIONS.map((section) => ({
      id: section.id,
      label: `${section.num} ${translate(uiLang(), section.titleKey)}`,
      value: summaries[section.id],
      required: section.id !== "study-sec-special",
      gaps: gaps[section.id],
    })),
    plan: {
      subject: draft.objects.map((item) => item.name.trim()).filter(Boolean).join("\n\n"),
      functional_unit: [
        draft.quantity.trim() && `数量：${draft.quantity.trim()}`,
        draft.unit.trim() && `单位：${draft.unit.trim()}`,
        draft.functionalSpec.trim() && `附加说明：${draft.functionalSpec.trim()}`,
      ]
        .filter(Boolean)
        .join("\n"),
      life_cycle_stages: [
        stages.length > 0 && `阶段：${stages.join(" → ")}`,
        draft.scopeNote.trim() && `附加说明：${draft.scopeNote.trim()}`,
      ].filter(Boolean).join("\n"),
      conditions: [
        draft.place.trim() && `地域与时间：${draft.place.trim()}`,
        databaseName.trim() && `LCA 数据库：${databaseName.trim()}`,
        draft.lcia.trim() && `环境影响评价方法：${draft.lcia.trim()}`,
        impact,
        draft.special.trim(),
      ]
        .filter(Boolean)
        .join("\n\n"),
    },
  };
}

export function emptyStudyWork(): StudyWork {
  return studyWork(blankDraft(), "", "");
}

function scrollContainer(main: HTMLElement) {
  if (main.scrollHeight > main.clientHeight + 1) return main;
  const parent = main.parentElement;
  if (parent && parent.scrollHeight > parent.clientHeight + 1) return parent;
  return main;
}

let objectSeq = 1;

function nextObjectId() {
  objectSeq += 1;
  return `object-${objectSeq}`;
}

export function StudyForm({
  source,
  sourceKey,
  onWork,
  templateSections,
}: {
  source: PlanFields;
  sourceKey: number;
  onWork?: (work: StudyWork) => void;
  /** YAML template sections; when set, only these blocks render / validate. */
  templateSections?: PlanTemplateSection[];
}) {
  const { t } = useLocale();
  const sectionMeta = templateSections?.length
    ? STUDY_SECTIONS.filter((section) => templateSections.some((item) => item.id === section.id))
    : STUDY_SECTIONS;
  const sectionRequired = new Map(
    (templateSections || []).map((item) => [item.id, item.required !== false] as const),
  );
  const sourceRef = useRef(source);
  sourceRef.current = source;
  const mainRef = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState<StudyDraft>(() => hydrate(source));
  const [unitCustom, setUnitCustom] = useState(false);
  const [openlcaOk, setOpenlcaOk] = useState<boolean | null>(null);
  const [databaseName, setDatabaseName] = useState("");
  const [checking, setChecking] = useState(false);
  const [activeSection, setActiveSection] = useState<(typeof STUDY_SECTIONS)[number]["id"]>(STUDY_SECTIONS[0].id);
  const onWorkRef = useRef(onWork);
  onWorkRef.current = onWork;

  useEffect(() => {
    setDraft(hydrate(sourceRef.current));
    setUnitCustom(false);
  }, [sourceKey]);

  useEffect(() => {
    void refreshOpenLca();
  }, []);

  useEffect(() => {
    const root = mainRef.current;
    if (!root) return;
    const update = () => {
      const scroller = scrollContainer(root);
      const origin = scroller.getBoundingClientRect().top;
      let current: (typeof STUDY_SECTIONS)[number]["id"] = (sectionMeta[0]?.id || STUDY_SECTIONS[0].id);
      for (const section of sectionMeta) {
        const element = document.getElementById(section.id);
        if (element && element.getBoundingClientRect().top - origin <= 48) current = section.id;
      }
      setActiveSection(current);
    };
    update();
    const scroller = scrollContainer(root);
    scroller.addEventListener("scroll", update, { passive: true });
    return () => scroller.removeEventListener("scroll", update);
  }, []);

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

  function commit(next: StudyDraft) {
    setDraft(next);
  }

  function patch(partial: Partial<StudyDraft>) {
    commit({ ...draft, ...partial });
  }

  function clearDraft() {
    setDraft(blankDraft());
    setUnitCustom(false);
  }

  function jumpTo(id: (typeof STUDY_SECTIONS)[number]["id"]) {
    const root = mainRef.current;
    const target = document.getElementById(id);
    if (!root || !target) return;
    setActiveSection(id);
    const scroller = scrollContainer(root);
    const top = scroller.scrollTop + target.getBoundingClientRect().top - scroller.getBoundingClientRect().top - 8;
    scroller.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }

  const databaseLabel = databaseName || (openlcaOk ? t("study.dbConnectedNoName") : openlcaOk === false ? t("study.disconnected") : t("study.reading"));
  const summaries = sectionSummaries(draft, databaseLabel);

  useEffect(() => {
    const work = studyWork(draft, databaseLabel, databaseName);
    if (!templateSections?.length) {
      onWorkRef.current?.(work);
      return;
    }
    const allowed = new Set(sectionMeta.map((section) => section.id));
    onWorkRef.current?.({
      ...work,
      rows: work.rows
        .filter((row) => allowed.has(row.id))
        .map((row) => ({
          ...row,
          required: sectionRequired.has(row.id) ? Boolean(sectionRequired.get(row.id)) : row.required,
          gaps: sectionRequired.get(row.id) === false ? [] : row.gaps,
        })),
    });
  }, [draft, databaseLabel, databaseName, templateSections, sectionMeta, sectionRequired]);

  return (
    <div className="plan-study">
      <div className="plan-study-main" ref={mainRef}>
        <section className="study-block" id="study-sec-subject" hidden={!sectionMeta.some((section) => section.id === "study-sec-subject")}>
          <div className="study-block-head">
            <h3>
              <span className="study-num">1</span>
              {t("study.subject")}
            </h3>
            <button
              type="button"
              className="study-text-button"
              onClick={() => patch({ objects: [...draft.objects, { id: nextObjectId(), name: "" }] })}
            >
              <Plus size={14} aria-hidden="true" />
              {t("study.addObject")}
            </button>
          </div>
          <p>{t("study.subjectHelp")}</p>
          <ul className="study-objects">
            {draft.objects.map((object, index) => (
              <li key={object.id}>
                {draft.objects.length > 1 ? <span>{index + 1}</span> : null}
                <textarea
                  className="study-area"
                  rows={3}
                  value={object.name}
                  placeholder={index === 0 ? t("study.phSubject") : t("study.phAlt")}
                  aria-label={t("study.subjectN", { n: index + 1 })}
                  onChange={(event) =>
                    patch({
                      objects: draft.objects.map((item) =>
                        item.id === object.id ? { ...item, name: event.target.value } : item,
                      ),
                    })
                  }
                />
                {draft.objects.length > 1 ? (
                  <button
                    type="button"
                    aria-label={t("study.removeSubjectN", { n: index + 1 })}
                    onClick={() => patch({ objects: draft.objects.filter((item) => item.id !== object.id) })}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </section>

        <section className="study-block" id="study-sec-basis" hidden={!sectionMeta.some((section) => section.id === "study-sec-basis")}>
          <h3>
            <span className="study-num">2</span>
            {t("study.fu")}
          </h3>
          <p>{t("study.fuHelp")}</p>
          <div className="study-fu">
            <label className="study-fu-qty" htmlFor="study-quantity">{t("study.qty")}</label>
            <label className="study-fu-unit" htmlFor="study-unit">{t("study.unit")}</label>
            <label className="study-fu-note" htmlFor="study-note">
              {t("study.extra")}
              <em>{t("study.optional")}</em>
            </label>
            <input
              id="study-quantity"
              className="study-fu-qty"
              type="text"
              inputMode="decimal"
              value={draft.quantity}
              placeholder="1,000"
              onChange={(event) => patch({ quantity: event.target.value })}
            />
            {unitCustom ? (
              <input
                id="study-unit"
                className="study-fu-unit"
                type="text"
                value={draft.unit}
                placeholder={t("study.enterUnit")}
                aria-label={t("study.unit")}
                autoFocus
                onChange={(event) => patch({ unit: event.target.value })}
                onBlur={(event) => {
                  if (!event.target.value.trim()) setUnitCustom(false);
                }}
              />
            ) : (
              <select
                id="study-unit"
                className="study-fu-unit"
                value={UNITS.includes(draft.unit) ? draft.unit : ""}
                onChange={(event) => {
                  if (event.target.value === CUSTOM_UNIT) {
                    setUnitCustom(true);
                    patch({ unit: "" });
                    return;
                  }
                  patch({ unit: event.target.value });
                }}
              >
                <option value="">{t("study.pickUnit")}</option>
                {UNITS.map((unit) => (
                  <option key={unit} value={unit}>
                    {unit}
                  </option>
                ))}
                <option value={CUSTOM_UNIT}>{t("study.manualUnit")}</option>
              </select>
            )}
            <textarea
              id="study-note"
              className="study-area study-fu-note"
              rows={1}
              value={draft.functionalSpec}
              placeholder={t("study.phFu")}
              onChange={(event) => patch({ functionalSpec: event.target.value })}
            />
          </div>
        </section>

        <section className="study-block" id="study-sec-life" hidden={!sectionMeta.some((section) => section.id === "study-sec-life")}>
          <h3>
            <span className="study-num">3</span>
            {t("study.scope")}
          </h3>
          <p>{t("study.scopeHelp")}</p>
          <div className="study-stages">
            {STAGES.map((stage, index) => {
              const Icon = stage.icon;
              const selected = draft.stages[stage.id];
              return (
                <span key={stage.id} className="study-stage-slot">
                  {index > 0 ? <span className="study-stage-arrow" aria-hidden="true">→</span> : null}
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() => patch({ stages: { ...draft.stages, [stage.id]: !selected } })}
                  >
                    <Icon size={15} aria-hidden="true" />
                    {t(stage.labelKey)}
                  </button>
                </span>
              );
            })}
          </div>
          <label className="study-stack" htmlFor="study-scope">
            <span>
              {t("study.extra")}
              <em>{t("study.optional")}</em>
            </span>
            <textarea
              id="study-scope"
              className="study-area"
              rows={3}
              value={draft.scopeNote}
              placeholder={t("study.phStages")}
              onChange={(event) => patch({ scopeNote: event.target.value })}
            />
          </label>
        </section>

        <section className="study-block" id="study-sec-place" hidden={!sectionMeta.some((section) => section.id === "study-sec-place")}>
          <h3>
            <span className="study-num">4</span>
            {t("study.geoTime")}
          </h3>
          <p>{t("study.geoHelp")}</p>
          <input
            className="study-place"
            type="text"
            aria-label={t("study.geoTime")}
            value={draft.place}
            placeholder={t("study.phGeo")}
            onChange={(event) => patch({ place: event.target.value })}
          />
        </section>

        <section className="study-block" id="study-sec-database" hidden={!sectionMeta.some((section) => section.id === "study-sec-database")}>
          <div className="study-block-head">
            <h3>
              <span className="study-num">5</span>
              {t("study.db")}
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
            aria-label={t("study.db")}
            value={databaseLabel}
          />
        </section>

        <section className="study-block" id="study-sec-lcia" hidden={!sectionMeta.some((section) => section.id === "study-sec-lcia")}>
          <div className="study-block-head">
            <h3>
              <span className="study-num">6</span>
              {t("study.lcia")}
            </h3>
            <span className={`study-link${openlcaOk ? " on" : ""}`}>
              {checking ? t("study.checking") : openlcaOk ? t("study.olcaOk") : t("study.olcaDown")}
              <button type="button" onClick={() => void refreshOpenLca()} disabled={checking}>
                {t("study.refresh")}
              </button>
            </span>
          </div>
          <p>{t("study.lciaHelp")}</p>
          <select aria-label={t("study.method")} value={draft.lcia} onChange={(event) => patch({ lcia: event.target.value })}>
            <option value="">{t("study.pickMethod")}</option>
            {LCIA_METHODS.map((method) => (
              <option key={method} value={method}>
                {method}
              </option>
            ))}
          </select>
        </section>

        <section className="study-block" id="study-sec-impact" hidden={!sectionMeta.some((section) => section.id === "study-sec-impact")}>
          <h3>
            <span className="study-num">7</span>
            {t("study.impacts")}
          </h3>
          <div className="study-radios" role="radiogroup" aria-label={t("study.impacts")}>
            <label>
              <input
                type="radio"
                name="impact-scope"
                checked={draft.impactScope === "all"}
                onChange={() => patch({ impactScope: "all" })}
              />
              {t("study.allIndicators")}
            </label>
            <label>
              <input
                type="radio"
                name="impact-scope"
                checked={draft.impactScope === "selected"}
                onChange={() => patch({ impactScope: "selected" })}
              />
              {t("study.onlyIndicators")}
            </label>
          </div>
          {draft.impactScope === "selected" ? (
            <input
              type="text"
              value={draft.impactNote}
              placeholder={t("study.phImpacts")}
              aria-label={t("study.impactIndicators")}
              onChange={(event) => patch({ impactNote: event.target.value })}
            />
          ) : null}
        </section>

        <section className="study-block" id="study-sec-special" hidden={!sectionMeta.some((section) => section.id === "study-sec-special")}>
          <h3>
            <span className="study-num">8</span>
            {t("study.special")}
          </h3>
          <p>{t("study.specialHelp")}</p>
          <textarea
            className="study-area"
            rows={5}
            value={draft.special}
            placeholder={t("study.noExtra")}
            onChange={(event) => patch({ special: event.target.value })}
          />
        </section>
      </div>

      <aside className="plan-study-side">
        <nav className="study-preview" aria-label={t("study.settings")}>
          <div className="study-preview-head">
            <h3>{t("study.previewTitle")}</h3>
            <button type="button" className="study-clear" onClick={clearDraft}>
              <Eraser size={14} aria-hidden="true" />
              {t("study.clear")}
            </button>
          </div>
          <p>{t("study.previewHelp")}</p>
          <ol className="study-nav">
            {sectionMeta.map((section) => {
              const summary = summaries[section.id];
              return (
                <li key={section.id}>
                  <button
                    type="button"
                    aria-current={activeSection === section.id ? "true" : undefined}
                    title={summary || undefined}
                    onClick={() => jumpTo(section.id)}
                  >
                    <strong>
                      <span className="study-num">{section.num}</span>
                      {t(section.titleKey)}
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
