"use client";

import { useEffect, useRef } from "react";
import type { ComponentType } from "react";
import { GearIcon } from "../launch-icons";
import { ModelsSection } from "../model-settings-dialog";
import { GeneralSection } from "./general-section";
import { SETTINGS_SECTIONS, settingsSection, type SettingsSectionId } from "./sections";
import { useSettings } from "./settings-context";

const PANELS: Record<SettingsSectionId, ComponentType<{ onChanged?: () => void }>> = {
  general: GeneralSection,
  models: ModelsSection,
};

function ActivePanel({
  section,
  onChanged,
}: {
  section: SettingsSectionId;
  onChanged: () => void;
}) {
  const Panel = PANELS[section];
  return <Panel onChanged={onChanged} />;
}

function dialogContainsPoint(dialog: HTMLDialogElement, x: number, y: number) {
  const rect = dialog.getBoundingClientRect();
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

export function SettingsButton() {
  const { openSettings } = useSettings();
  return (
    <button type="button" className="settings-launch" aria-label="设置" title="设置" onClick={() => openSettings()}>
      <GearIcon />
    </button>
  );
}

export function SettingsDialog() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const { open, section, setSection, closeSettings, notifyChanged } = useSettings();
  const current = settingsSection(section);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="settings-dialog"
      aria-labelledby="settings-dialog-title"
      onClose={closeSettings}
      onClick={(event) => {
        const dialog = dialogRef.current;
        if (!dialog) return;
        if (!dialogContainsPoint(dialog, event.clientX, event.clientY)) closeSettings();
      }}
    >
      <div className="settings-frame">
        <nav className="settings-nav" aria-label="设置">
          <p id="settings-dialog-title" className="settings-nav-label">
            设置
          </p>
          {SETTINGS_SECTIONS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-current={item.id === section ? "page" : undefined}
              onClick={() => setSection(item.id as SettingsSectionId)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="settings-main">
          <header className="settings-main-head">
            <div>
              <p className="settings-crumb">设置 / {current.label}</p>
              <h2>{current.title}</h2>
            </div>
            <button type="button" onClick={closeSettings}>
              关闭
            </button>
          </header>
          <div className="settings-body">
            {open ? <ActivePanel section={section} onChanged={notifyChanged} /> : null}
          </div>
        </div>
      </div>
    </dialog>
  );
}
