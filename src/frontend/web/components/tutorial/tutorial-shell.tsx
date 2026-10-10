"use client";

import { useEffect, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { readTutorialReturn } from "../return-to";

export type TutorialEntry = {
  path: string;
  label: string;
};

export type TutorialGroup = {
  id: string;
  label: string;
  entries: TutorialEntry[];
};

export type TutorialCatalog = {
  groups: TutorialGroup[];
};

export type TutorialDocument = {
  path: string;
  label: string;
  title: string;
  kind: "markdown";
  content: string;
};

function hrefFor(path: string) {
  const bare = path.replace(/\.md$/i, "");
  return `/tutorial/${bare}`;
}

type TutorialShellProps = {
  catalog: TutorialCatalog | null;
  selected: string;
  error?: string;
  title?: string;
  crumbPath?: string;
  children: ReactNode;
};

export function TutorialShell({
  catalog,
  selected,
  error = "",
  title,
  crumbPath,
  children,
}: TutorialShellProps) {
  const router = useRouter();
  const located = findEntry(catalog, selected);
  const heading =
    title || located?.entry.label || (error ? "教程" : catalog ? "教程" : "教程");

  useEffect(() => {
    // Reuse status-fit so shell width/height match the status page.
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  return (
    <section className="tutorial-panel settings-card">
      <div className="tutorial-frame">
        <nav className="settings-nav harness-nav tutorial-nav" aria-label="教程">
          <p className="settings-nav-label">教程</p>
          {catalog?.groups.map((group) => (
            <div key={group.id}>
              {catalog.groups.length > 1 || group.id !== "overview" ? (
                <p className="harness-nav-group">{group.label}</p>
              ) : null}
              {group.entries.map((entry) => (
                <Link
                  key={entry.path}
                  href={hrefFor(entry.path)}
                  aria-current={entry.path === selected ? "page" : undefined}
                  data-active={entry.path === selected ? "true" : undefined}
                >
                  {entry.label}
                </Link>
              ))}
            </div>
          ))}
          {!catalog && !error ? <p className="harness-status">加载目录…</p> : null}
        </nav>
        <div className="settings-main tutorial-main">
          <header className="settings-main-head tutorial-main-head">
            <div>
              <p className="settings-crumb">
                {["教程", located?.group.label, located?.entry.label].filter(Boolean).join(" / ")}
              </p>
              <h2>{heading}</h2>
              {crumbPath ? <p className="harness-path mono">{crumbPath}</p> : null}
            </div>
            <button
              type="button"
              className="tutorial-close"
              aria-label="关闭教程"
              title="返回上一页"
              onClick={() => router.push(readTutorialReturn())}
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

function findEntry(catalog: TutorialCatalog | null, path: string) {
  if (!catalog || !path) return null;
  for (const group of catalog.groups) {
    const entry = group.entries.find((item) => item.path === path);
    if (entry) return { group, entry };
  }
  return null;
}
