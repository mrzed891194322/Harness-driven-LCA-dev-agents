"use client";

import { Activity, ClipboardList, FolderOpen, Terminal } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale } from "../lib/i18n/locale-context";

const LINKS = [
  { href: "/status", key: "nav.status", icon: Activity },
  { href: "/plan", key: "nav.plan", icon: ClipboardList },
  { href: "/runs", key: "nav.runs", icon: Terminal },
  { href: "/results", key: "nav.results", icon: FolderOpen },
] as const;

export function AppNav() {
  const path = usePathname();
  const { t } = useLocale();
  return (
    <nav className="nav-row">
      {LINKS.map((link) => {
        const Icon = link.icon;
        return (
          <Link
            key={link.href}
            href={link.href}
            data-active={path === link.href ? "true" : undefined}
          >
            <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
            {t(link.key)}
          </Link>
        );
      })}
    </nav>
  );
}
