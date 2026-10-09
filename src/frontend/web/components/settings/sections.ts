export const SETTINGS_SECTIONS = [
  { id: "general", label: "通用", title: "端口设置" },
  { id: "models", label: "模型", title: "Provider 配置" },
] as const;

export type SettingsSectionId = (typeof SETTINGS_SECTIONS)[number]["id"];

export function settingsSection(id: SettingsSectionId) {
  return SETTINGS_SECTIONS.find((item) => item.id === id) ?? SETTINGS_SECTIONS[0];
}
