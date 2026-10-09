"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen } from "lucide-react";

export function TutorialButton() {
  const path = usePathname();
  const active = path === "/tutorial" || path.startsWith("/tutorial/");
  return (
    <Link
      href="/tutorial"
      className="settings-launch"
      aria-label="教程"
      title="教程"
      aria-current={active ? "page" : undefined}
      data-active={active ? "true" : undefined}
    >
      <BookOpen size={16} aria-hidden="true" className="launch-icon" />
      <span>教程</span>
    </Link>
  );
}
