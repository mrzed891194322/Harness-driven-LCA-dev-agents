"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen } from "lucide-react";
import { rememberTutorialReturn } from "./return-to";

export function TutorialButton() {
  const path = usePathname();
  const active = path === "/tutorial" || path.startsWith("/tutorial/");

  useEffect(() => {
    rememberTutorialReturn(path);
  }, [path]);
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
