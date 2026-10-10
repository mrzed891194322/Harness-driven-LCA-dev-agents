"use client";

import { useEffect, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { readHarnessReturn } from "../return-to";

export type HarnessEntry = {
  path: string;
  label: string;
};

export type HarnessGroup = {
  id: string;
  label: string;
  entries: HarnessEntry[];
};

export type HarnessSection = {
  id: string;
  label: string;
  groups: HarnessGroup[];
};

export type HarnessCatalog = {
  sections: HarnessSection[];
};

export function harnessHref(path: string) {
  return `/harness/${path.split("/").map((part) => encodeURIComponent(part)).join("/")}`;
}

export function findHarnessEntry(catalog: HarnessCatalog | null, path: string) {
  if (!catalog || !path) return null;
  for (const section of catalog.sections) {
    for (const group of section.groups) {
      const entry = group.entries.find((item) => item.path === path);
      if (entry) return { section, group, entry };
    }
  }
  return null;
}

type HarnessShellProps = {
  catalog: HarnessCatalog | null;
  selected: string;
  error?: string;
  title?: string;
  crumbPath?: string;
  children: ReactNode;
};

export function HarnessShell({
  catalog,
  selected,
  error = "",
  title,
  crumbPath,
  children,
}: HarnessShellProps) {
  const router = useRouter();
  const located = findHarnessEntry(catalog, selected);
  const heading = title || located?.entry.label || "Harness";
  const crumb = located
    ? ["Harness", located.section.label, located.group.label, located.entry.label].join(" / ")
    : "Harness";

  useEffect(() => {
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  useEffect(() => {
    document.querySelector(".tutorial-body")?.scrollTo(0, 0);
  }, [selected]);

  return (
    <section className="tutorial-panel settings-card">
      <div className="tutorial-frame">
        <nav className="settings-nav harness-nav tutorial-nav" aria-label="Harness">
          <p className="settings-nav-label">Harness</p>
          {catalog?.sections.map((section) => (
            <div key={section.id}>
              <p className="harness-nav-section">{section.label}</p>
              {section.groups.map((group) => (
                <div key={group.id}>
                  {section.groups.length > 1 || group.id !== "overview" ? (
                    <p className="harness-nav-group">{group.label}</p>
                  ) : null}
                  {group.entries.map((entry) => (
                    <Link
                      key={entry.path}
                      href={harnessHref(entry.path)}
                      aria-current={entry.path === selected ? "page" : undefined}
                      data-active={entry.path === selected ? "true" : undefined}
                    >
                      {entry.label}
                    </Link>
                  ))}
                </div>
              ))}
            </div>
          ))}
          {!catalog && !error ? <p className="harness-status">加载目录…</p> : null}
        </nav>
        <div className="settings-main tutorial-main">
          <header className="settings-main-head tutorial-main-head">
            <div>
              <p className="settings-crumb">{error ? "Harness" : crumb}</p>
              <h2>{heading}</h2>
              {crumbPath ? <p className="harness-path mono">{crumbPath}</p> : null}
            </div>
            <button
              type="button"
              className="tutorial-close"
              aria-label="关闭 Harness"
              title="返回上一页"
              onClick={() => router.push(readHarnessReturn())}
            >
              <X size={18} aria-hidden="true" />
            </button>
          </header>
          <div className="settings-body tutorial-body">{children}</div>
        </div>
      </div>
    </section>
  );
}
