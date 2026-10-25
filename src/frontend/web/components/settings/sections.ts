export const SETTINGS_SECTIONS = [
  { id: "general", labelKey: "settings.general", titleKey: "settings.generalTitle" },
  { id: "models", labelKey: "settings.models", titleKey: "settings.modelsTitle" },
] as const;

export type SettingsSectionId = (typeof SETTINGS_SECTIONS)[number]["id"];

export function settingsSection(id: SettingsSectionId) {
  return SETTINGS_SECTIONS.find((item) => item.id === id) ?? SETTINGS_SECTIONS[0];
}
