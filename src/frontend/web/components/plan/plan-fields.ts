import { translate } from "../../lib/i18n/messages";
import { uiLang } from "../../lib/run-status";

export type PlanFields = {
  subject: string;
  functional_unit: string;
  life_cycle_stages: string;
  conditions: string;
};

export const PLAN_FIELD_ROWS: { key: keyof PlanFields; labelKey: string; required: boolean }[] = [
  { key: "subject", labelKey: "plan.field.subject", required: true },
  { key: "functional_unit", labelKey: "plan.field.fu", required: true },
  { key: "life_cycle_stages", labelKey: "plan.field.stages", required: true },
  { key: "conditions", labelKey: "plan.field.conditions", required: false },
];

export function planFieldLabel(labelKey: string): string {
  return translate(uiLang(), labelKey);
}

export function missingPlanFields(fields: PlanFields): string[] {
  const gaps: string[] = [];
  for (const row of PLAN_FIELD_ROWS) {
    if (row.required && !fields[row.key]?.trim()) gaps.push(planFieldLabel(row.labelKey));
  }
  return gaps;
}
