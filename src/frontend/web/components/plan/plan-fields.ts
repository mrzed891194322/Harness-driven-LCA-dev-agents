export type PlanFields = {
  subject: string;
  functional_unit: string;
  life_cycle_stages: string;
  conditions: string;
};

export const PLAN_FIELD_ROWS: { key: keyof PlanFields; label: string; required: boolean }[] = [
  { key: "subject", label: "研究对象", required: true },
  { key: "functional_unit", label: "功能单位", required: true },
  { key: "life_cycle_stages", label: "生命周期阶段", required: true },
  { key: "conditions", label: "附加条件", required: false },
];

export function missingPlanFields(fields: PlanFields): string[] {
  const gaps: string[] = [];
  for (const row of PLAN_FIELD_ROWS) {
    if (row.required && !fields[row.key]?.trim()) gaps.push(row.label);
  }
  return gaps;
}
