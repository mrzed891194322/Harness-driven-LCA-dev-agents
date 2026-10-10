"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Lasso } from "lucide-react";
import { rememberHarnessReturn } from "../return-to";

export function HarnessButton() {
  const path = usePathname();
  const active = path === "/harness" || path.startsWith("/harness/");

  useEffect(() => {
    rememberHarnessReturn(path);
  }, [path]);

  return (
    <Link
      href="/harness"
      className="settings-launch"
      aria-label="Harness"
      title="Harness"
      aria-current={active ? "page" : undefined}
      data-active={active ? "true" : undefined}
    >
      <Lasso size={16} aria-hidden="true" className="launch-icon" />
      <span>Harness</span>
    </Link>
  );
}
