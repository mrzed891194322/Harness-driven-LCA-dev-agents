export type ModelRow = {
  id: string;
  label?: string;
  provider_name?: string;
  reasoning?: boolean;
  thinking_levels?: string[];
};
export type ModelChoice = { value: string; label: string };

/**
 * Options for the /runs model dropdown. `current` is the saved default as a
 * provider/model ref (default_ref); it stays selectable even when its provider
 * did not list it, so the select never silently shows another model.
 */
export function modelChoices(models: ModelRow[], current: string): { choices: ModelChoice[]; value: string } {
  const choices = models.map((m) => ({
    value: m.id,
    label: m.provider_name ? `${m.provider_name} · ${m.label || m.id}` : m.label || m.id,
  }));
  if (current && !choices.some((c) => c.value === current)) {
    choices.unshift({ value: current, label: `${current}（当前）` });
  }
  if (!current) choices.unshift({ value: "", label: "未选择模型" });
  return { choices, value: current };
}
