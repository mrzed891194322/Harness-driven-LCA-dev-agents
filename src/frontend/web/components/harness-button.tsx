"use client";

import { useLocale } from "../lib/i18n/locale-context";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileCode2 } from "lucide-react";

export function HarnessButton() {
  const { t } = useLocale();
  const path = usePathname();
  const active = path === "/harness";
  return (
    <Link
      href="/harness"
      className="settings-launch"
      aria-label={t("chrome.harness")}
      title={t("chrome.harness")}
      data-testid="header-harness"
      aria-current={active ? "page" : undefined}
      data-active={active ? "true" : undefined}
    >
      <FileCode2 size={16} aria-hidden="true" className="launch-icon" />
      <span>{t("chrome.harness")}</span>
    </Link>
  );
}
