"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/status", label: "项目状态" },
  { href: "/plan", label: "LCA 计划" },
  { href: "/runs", label: "运行详情" },
  { href: "/results", label: "结果与历史" },
];

export function AppNav() {
  const path = usePathname();
  return (
    <nav className="nav-row">
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          data-active={path === link.href ? "true" : undefined}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
