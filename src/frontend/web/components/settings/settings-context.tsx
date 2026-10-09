"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { SETTINGS_SECTIONS, type SettingsSectionId } from "./sections";

type SettingsContextValue = {
  open: boolean;
  section: SettingsSectionId;
  revision: number;
  openSettings: (section?: SettingsSectionId) => void;
  closeSettings: () => void;
  setSection: (section: SettingsSectionId) => void;
  notifyChanged: () => void;
};

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [section, setSection] = useState<SettingsSectionId>(SETTINGS_SECTIONS[0].id);
  const [revision, setRevision] = useState(0);

  const openSettings = useCallback((next?: SettingsSectionId) => {
    if (next) setSection(next);
    setOpen(true);
  }, []);

  const closeSettings = useCallback(() => setOpen(false), []);
  const notifyChanged = useCallback(() => setRevision((value) => value + 1), []);

  const value = useMemo(
    () => ({
      open,
      section,
      revision,
      openSettings,
      closeSettings,
      setSection,
      notifyChanged,
    }),
    [open, section, revision, openSettings, closeSettings, notifyChanged],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  const value = useContext(SettingsContext);
  if (!value) throw new Error("useSettings must be used within SettingsProvider");
  return value;
}
