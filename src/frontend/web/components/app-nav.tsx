"use client";

import { Activity, ClipboardList, History, Terminal } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/status", label: "项目状态", icon: Activity },
  { href: "/plan", label: "LCA 计划", icon: ClipboardList },
  { href: "/runs", label: "运行详情", icon: Terminal },
  { href: "/results", label: "结果与历史", icon: History },
];

export function AppNav() {
  const path = usePathname();
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
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
