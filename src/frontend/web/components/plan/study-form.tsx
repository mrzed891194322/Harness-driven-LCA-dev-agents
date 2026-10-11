"use client";

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
  geography: string;
  year: string;
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

const STAGES: { id: StageId; label: string; icon: LucideIcon }[] = [
  { id: "raw", label: "原材料获取", icon: Leaf },
  { id: "make", label: "制造", icon: Factory },
  { id: "ship", label: "配送", icon: Truck },
  { id: "use", label: "使用", icon: UserRound },
  { id: "end", label: "最终处置", icon: Recycle },
];

const REGIONS = ["德国", "中国", "土耳其", "欧洲", "全球"];

const STUDY_SECTIONS = [
  { id: "study-sec-subject", num: "1", title: "研究对象" },
  { id: "study-sec-basis", num: "2", title: "计算基准（功能单位）" },
  { id: "study-sec-life", num: "3", title: "生命周期范围" },
  { id: "study-sec-place", num: "4", title: "地域与时间" },
  { id: "study-sec-database", num: "5", title: "LCA 数据库" },
  { id: "study-sec-lcia", num: "6", title: "环境影响评价方法（LCIA）" },
  { id: "study-sec-impact", num: "7", title: "关注的环境影响" },
  { id: "study-sec-special", num: "8", title: "特殊要求" },
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
    geography: "",
    year: "",
    lcia: "",
    impactScope: "all",
    impactNote: "",
    special: "",
  };
}

function hydrate(fields: PlanFields): StudyDraft {
  const filled = [fields.subject, fields.functional_unit, fields.life_cycle_stages, fields.conditions].some((item) =>
    item.trim(),
  );
  if (!filled) return blankDraft();
  return {
    ...blankDraft(),
    objects: [{ id: "object-1", name: fields.subject }],
    unit: "",
    functionalSpec: fields.functional_unit,
    scopeNote: fields.life_cycle_stages,
    special: fields.conditions,
  };
}

function filledLines(lines: Array<string | false>) {
  return lines.filter((line): line is string => Boolean(line)).join("\n");
}

function sectionSummaries(draft: StudyDraft, database: string) {
  const objects = draft.objects.map((item) => item.name.trim()).filter(Boolean);
  const stages = STAGES.filter((stage) => draft.stages[stage.id]).map((stage) => stage.label);
  return {
    "study-sec-subject": objects.join("\n"),
    "study-sec-basis": filledLines([
      draft.quantity.trim() && `数量：${draft.quantity.trim()}`,
      draft.unit.trim() && `单位：${draft.unit.trim()}`,
      draft.functionalSpec.trim() && `附加说明：${draft.functionalSpec.trim()}`,
    ]),
    "study-sec-life": filledLines([
      stages.length > 0 && stages.join(" → "),
      draft.scopeNote.trim() && `附加说明：${draft.scopeNote.trim()}`,
    ]),
    "study-sec-place": filledLines([
      draft.geography.trim() && `地域：${draft.geography.trim()}`,
      draft.year.trim() && `研究年份：${draft.year.trim()}`,
    ]),
    "study-sec-database": database.trim(),
    "study-sec-lcia": draft.lcia.trim(),
    "study-sec-impact":
      draft.impactScope === "selected"
        ? filledLines(["仅指定指标", draft.impactNote.trim() && draft.impactNote.trim()])
        : "所选方法的全部指标",
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
    "study-sec-subject": objects.length > 0 && objects.every(Boolean) ? [] : ["研究对象"],
    "study-sec-basis": [draft.quantity.trim() ? "" : "数量", draft.unit.trim() ? "" : "单位"].filter(Boolean),
    "study-sec-life": stagePicked ? [] : ["生命周期阶段"],
    "study-sec-place": [draft.geography.trim() ? "" : "地域", draft.year.trim() ? "" : "研究年份"].filter(Boolean),
    "study-sec-database": databaseName.trim() ? [] : ["LCA 数据库"],
    "study-sec-lcia": draft.lcia.trim() ? [] : ["环境影响评价方法"],
    "study-sec-impact": draft.impactScope === "selected" && !draft.impactNote.trim() ? ["指定指标"] : [],
    "study-sec-special": [],
  };
}

export function studyWork(draft: StudyDraft, databaseLabel: string, databaseName: string): StudyWork {
  const summaries = sectionSummaries(draft, databaseLabel);
  const gaps = gapList(draft, databaseName);
  const stages = STAGES.filter((stage) => draft.stages[stage.id]).map((stage) => stage.label);
  const impact =
    draft.impactScope === "selected"
      ? ["仅指定指标", draft.impactNote.trim()].filter(Boolean).join("：")
      : "所选方法的全部指标";
  return {
    rows: STUDY_SECTIONS.map((section) => ({
      id: section.id,
      label: `${section.num} ${section.title}`,
      value: summaries[section.id],
      required: section.id !== "study-sec-special",
      gaps: gaps[section.id],
    })),
    plan: {
      subject: draft.objects.map((item) => item.name.trim()).filter(Boolean).join("\n"),
      functional_unit: [
        draft.quantity.trim() && `数量：${draft.quantity.trim()}`,
        draft.unit.trim() && `单位：${draft.unit.trim()}`,
        draft.functionalSpec.trim(),
      ]
        .filter(Boolean)
        .join("\n"),
      life_cycle_stages: [stages.join(" → "), draft.scopeNote.trim()].filter(Boolean).join("\n"),
      conditions: [
        draft.geography.trim() && `地域：${draft.geography.trim()}`,
        draft.year.trim() && `研究年份：${draft.year.trim()}`,
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
}: {
  source: PlanFields;
  sourceKey: number;
  onWork?: (work: StudyWork) => void;
}) {
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
      let current: (typeof STUDY_SECTIONS)[number]["id"] = STUDY_SECTIONS[0].id;
      for (const section of STUDY_SECTIONS) {
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

  const databaseLabel = databaseName || (openlcaOk ? "已连接，未能读取数据库名称" : openlcaOk === false ? "未连接" : "正在读取…");
  const summaries = sectionSummaries(draft, databaseLabel);

  useEffect(() => {
    onWorkRef.current?.(studyWork(draft, databaseLabel, databaseName));
  }, [draft, databaseLabel, databaseName]);

  return (
    <div className="plan-study">
      <div className="plan-study-main" ref={mainRef}>
        <section className="study-block" id="study-sec-subject">
          <div className="study-block-head">
            <h3>
              <span className="study-num">1</span>
              研究对象
            </h3>
            <button
              type="button"
              className="study-text-button"
              onClick={() => patch({ objects: [...draft.objects, { id: nextObjectId(), name: "" }] })}
            >
              <Plus size={14} aria-hidden="true" />
              添加对象
            </button>
          </div>
          <p>填写要评估的对象。有多个对象时，点击添加对象。</p>
          <ul className="study-objects">
            {draft.objects.map((object, index) => (
              <li key={object.id}>
                {draft.objects.length > 1 ? <span>{index + 1}</span> : null}
                <textarea
                  className="study-area"
                  rows={3}
                  value={object.name}
                  placeholder={index === 0 ? "例如：1 L PET 瓶装静水（PET 瓶、HDPE 瓶盖、PP 标签）" : "例如：另一种原料、产地或工艺"}
                  aria-label={`研究对象 ${index + 1}`}
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
                    aria-label={`移除研究对象 ${index + 1}`}
                    onClick={() => patch({ objects: draft.objects.filter((item) => item.id !== object.id) })}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </section>

        <section className="study-block" id="study-sec-basis">
          <h3>
            <span className="study-num">2</span>
            计算基准（功能单位）
          </h3>
          <p>按多少产品或服务计算？必要时请说明功能或性能条件。</p>
          <div className="study-fu">
            <label className="study-fu-qty" htmlFor="study-quantity">数量</label>
            <label className="study-fu-unit" htmlFor="study-unit">单位</label>
            <label className="study-fu-note" htmlFor="study-note">
              附加说明
              <em>可选</em>
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
                placeholder="输入单位"
                aria-label="单位"
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
                <option value="">选择单位</option>
                {UNITS.map((unit) => (
                  <option key={unit} value={unit}>
                    {unit}
                  </option>
                ))}
                <option value={CUSTOM_UNIT}>手动填写</option>
              </select>
            )}
            <textarea
              id="study-note"
              className="study-area study-fu-note"
              rows={1}
              value={draft.functionalSpec}
              placeholder="例如：每瓶 1 L，在德国销售点交付"
              onChange={(event) => patch({ functionalSpec: event.target.value })}
            />
          </div>
        </section>

        <section className="study-block" id="study-sec-life">
          <h3>
            <span className="study-num">3</span>
            生命周期范围
          </h3>
          <p>从哪里开始，算到哪里？请选择系统边界。</p>
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
                    {stage.label}
                  </button>
                </span>
              );
            })}
          </div>
          <label className="study-stack" htmlFor="study-scope">
            <span>
              附加说明
              <em>可选</em>
            </span>
            <textarea
              id="study-scope"
              className="study-area"
              rows={3}
              value={draft.scopeNote}
              placeholder="例如：从原料获取到德国销售点交付，不包括消费者使用和最终处置"
              onChange={(event) => patch({ scopeNote: event.target.value })}
            />
          </label>
        </section>

        <section className="study-block" id="study-sec-place">
          <h3>
            <span className="study-num">4</span>
            地域与时间
          </h3>
          <p>如有指定的目标市场、地区或研究年份，请在此说明。</p>
          <div className="study-place">
            <label>
              地域
              <input
                type="text"
                list="study-regions"
                value={draft.geography}
                placeholder="例如：德国"
                onChange={(event) => patch({ geography: event.target.value })}
              />
              <datalist id="study-regions">
                {REGIONS.map((region) => (
                  <option key={region} value={region} />
                ))}
              </datalist>
            </label>
            <label>
              研究年份
              <input
                type="text"
                value={draft.year}
                placeholder="例如 2024 或 2020–2024"
                onChange={(event) => patch({ year: event.target.value })}
              />
            </label>
          </div>
        </section>

        <section className="study-block" id="study-sec-database">
          <div className="study-block-head">
            <h3>
              <span className="study-num">5</span>
              LCA 数据库
            </h3>
            <span className={`study-link${openlcaOk ? " on" : ""}`}>
              {checking ? "正在检查…" : openlcaOk ? "已连接 openLCA" : "未连接 openLCA"}
              <button type="button" onClick={() => void refreshOpenLca()} disabled={checking}>
                刷新
              </button>
            </span>
          </div>
          <p>若需更改，请在openLCA界面手动执行</p>
          <input
            className="study-locked"
            type="text"
            readOnly
            aria-readonly="true"
            aria-label="LCA 数据库"
            value={databaseLabel}
          />
        </section>

        <section className="study-block" id="study-sec-lcia">
          <div className="study-block-head">
            <h3>
              <span className="study-num">6</span>
              环境影响评价方法（LCIA）
            </h3>
            <span className={`study-link${openlcaOk ? " on" : ""}`}>
              {checking ? "正在检查…" : openlcaOk ? "已连接 openLCA" : "未连接 openLCA"}
              <button type="button" onClick={() => void refreshOpenLca()} disabled={checking}>
                刷新
              </button>
            </span>
          </div>
          <p>选择当前openLCA数据库中可用的方法</p>
          <select aria-label="环境影响评价方法" value={draft.lcia} onChange={(event) => patch({ lcia: event.target.value })}>
            <option value="">选择评价方法</option>
            {LCIA_METHODS.map((method) => (
              <option key={method} value={method}>
                {method}
              </option>
            ))}
          </select>
        </section>

        <section className="study-block" id="study-sec-impact">
          <h3>
            <span className="study-num">7</span>
            关注的环境影响
          </h3>
          <div className="study-radios" role="radiogroup" aria-label="关注的环境影响">
            <label>
              <input
                type="radio"
                name="impact-scope"
                checked={draft.impactScope === "all"}
                onChange={() => patch({ impactScope: "all" })}
              />
              所选方法的全部指标
            </label>
            <label>
              <input
                type="radio"
                name="impact-scope"
                checked={draft.impactScope === "selected"}
                onChange={() => patch({ impactScope: "selected" })}
              />
              仅指定指标
            </label>
          </div>
          {draft.impactScope === "selected" ? (
            <input
              type="text"
              value={draft.impactNote}
              placeholder="例如：气候变化、水资源消耗"
              aria-label="指定的环境影响指标"
              onChange={(event) => patch({ impactNote: event.target.value })}
            />
          ) : null}
        </section>

        <section className="study-block" id="study-sec-special">
          <h3>
            <span className="study-num">8</span>
            特殊要求
          </h3>
          <p>例如：指定数据库、遵循的标准、需要分析的特殊情景或其他限制。</p>
          <textarea
            className="study-area"
            rows={5}
            value={draft.special}
            placeholder="没有额外限制时留空"
            onChange={(event) => patch({ special: event.target.value })}
          />
        </section>
      </div>

      <aside className="plan-study-side">
        <nav className="study-preview" aria-label="研究设定">
          <div className="study-preview-head">
            <h3>研究设定预览</h3>
            <button type="button" className="study-clear" onClick={clearDraft}>
              <Eraser size={14} aria-hidden="true" />
              清空
            </button>
          </div>
          <p>点击条目，跳到左侧对应位置。</p>
          <ol className="study-nav">
            {STUDY_SECTIONS.map((section) => {
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
                      {section.title}
                    </strong>
                    <span className={summary ? undefined : "is-empty"}>{summary || "未填写"}</span>
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
