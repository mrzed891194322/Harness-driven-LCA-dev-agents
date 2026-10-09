"use client";

import { useEffect, useRef, useState } from "react";
import { SaddleIcon } from "../launch-icons";
import { MarkdownView } from "./markdown-view";
import { useHarness } from "./harness-context";

type HarnessEntry = {
  path: string;
  label: string;
};

type HarnessGroup = {
  id: string;
  label: string;
  entries: HarnessEntry[];
};

type HarnessSection = {
  id: string;
  label: string;
  groups: HarnessGroup[];
};

type HarnessCatalog = {
  sections: HarnessSection[];
};

type HarnessDocument = {
  path: string;
  label: string;
  title: string;
  kind: "markdown" | "yaml" | "json";
  content: string;
};

function dialogContainsPoint(dialog: HTMLDialogElement, x: number, y: number) {
  const rect = dialog.getBoundingClientRect();
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

function firstEntry(catalog: HarnessCatalog | null) {
  return catalog?.sections[0]?.groups[0]?.entries[0] ?? null;
}

function findEntry(catalog: HarnessCatalog | null, path: string) {
  if (!catalog) return null;
  for (const section of catalog.sections) {
    for (const group of section.groups) {
      const entry = group.entries.find((item) => item.path === path);
      if (entry) return { section, group, entry };
    }
  }
  return null;
}

function resolveRelative(currentPath: string, href: string) {
  const clean = href.split("#")[0].split("?")[0];
  if (!clean) return null;
  const parts = currentPath.split("/").slice(0, -1);
  for (const part of clean.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") parts.pop();
    else parts.push(part);
  }
  const next = parts.join("/");
  return next || null;
}

export function HarnessButton() {
  const { openHarness } = useHarness();
  return (
    <button type="button" className="settings-launch" aria-label="Harness" title="Harness" onClick={() => openHarness()}>
      <SaddleIcon />
      <span>Harness</span>
    </button>
  );
}

export function HarnessDialog() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const { open, closeHarness } = useHarness();
  const [catalog, setCatalog] = useState<HarnessCatalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [selected, setSelected] = useState("");
  const [doc, setDoc] = useState<HarnessDocument | null>(null);
  const [documentError, setDocumentError] = useState("");
  const [loadingDoc, setLoadingDoc] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  useEffect(() => {
    if (!open || catalog) return;
    let cancelled = false;
    fetch("/api/harness/catalog")
      .then(async (response) => {
        const data = (await response.json()) as HarnessCatalog & { detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法加载 Harness 目录");
        return data;
      })
      .then((data) => {
        if (cancelled) return;
        setCatalog(data);
        setCatalogError("");
        setSelected((current) => current || firstEntry(data)?.path || "");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setCatalogError(error instanceof Error ? error.message : "无法加载 Harness 目录");
      });
    return () => {
      cancelled = true;
    };
  }, [open, catalog]);

  useEffect(() => {
    if (!open || !selected) return;
    let cancelled = false;
    setLoadingDoc(true);
    setDocumentError("");
    fetch(`/api/harness/document?path=${encodeURIComponent(selected)}`)
      .then(async (response) => {
        const data = (await response.json()) as HarnessDocument & { detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法读取文档");
        return data;
      })
      .then((data) => {
        if (cancelled) return;
        setDoc(data);
        setLoadingDoc(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setDoc(null);
        setLoadingDoc(false);
        setDocumentError(error instanceof Error ? error.message : "无法读取文档");
      });
    return () => {
      cancelled = true;
    };
  }, [open, selected]);

  useEffect(() => {
    if (open) bodyRef.current?.scrollTo(0, 0);
  }, [open, selected]);

  const located = findEntry(catalog, selected);
  const crumb = located
    ? ["Harness", located.section.label, located.group.label, located.entry.label].join(" / ")
    : "Harness";

  function openRelative(href: string) {
    if (!selected || !catalog) return;
    const next = resolveRelative(selected, href);
    if (next && findEntry(catalog, next)) setSelected(next);
  }

  return (
    <dialog
      ref={dialogRef}
      className="settings-dialog harness-dialog"
      aria-labelledby="harness-dialog-title"
      onClose={closeHarness}
      onClick={(event) => {
        const dialog = dialogRef.current;
        if (!dialog) return;
        if (!dialogContainsPoint(dialog, event.clientX, event.clientY)) closeHarness();
      }}
    >
      <div className="settings-frame">
        <nav className="settings-nav harness-nav" aria-label="Harness">
          <p id="harness-dialog-title" className="settings-nav-label">
            Harness
          </p>
          {catalog?.sections.map((section) => (
            <div key={section.id}>
              <p className="harness-nav-section">{section.label}</p>
              {section.groups.map((group) => (
                <div key={group.id}>
                  {section.groups.length > 1 || group.id !== "overview" ? (
                    <p className="harness-nav-group">{group.label}</p>
                  ) : null}
                  {group.entries.map((entry) => (
                    <button
                      key={entry.path}
                      type="button"
                      aria-current={entry.path === selected ? "page" : undefined}
                      onClick={() => setSelected(entry.path)}
                    >
                      {entry.label}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </nav>
        <div className="settings-main">
          <header className="settings-main-head">
            <div>
              <p className="settings-crumb">{crumb}</p>
              <h2>{doc?.path === selected ? doc.title : located?.entry.label || "Harness"}</h2>
              {located ? <p className="harness-path mono">{located.entry.path}</p> : null}
            </div>
            <button type="button" onClick={closeHarness}>
              关闭
            </button>
          </header>
          <div className="settings-body" ref={bodyRef}>
            {catalogError ? <p className="harness-status">{catalogError}</p> : null}
            {!catalog && !catalogError && open ? <p className="harness-status">正在加载目录…</p> : null}
            {catalog && catalog.sections.length === 0 ? (
              <p className="harness-status">harness 目录里没有可显示的文档。</p>
            ) : null}
            {documentError ? <p className="harness-status">{documentError}</p> : null}
            {loadingDoc && doc?.path !== selected ? <p className="harness-status">正在读取…</p> : null}
            {doc && doc.path === selected && doc.kind === "markdown" ? (
              <MarkdownView source={doc.content} onOpen={openRelative} />
            ) : null}
            {doc && doc.path === selected && doc.kind !== "markdown" ? (
              <pre className="harness-source">
                <code>{doc.content}</code>
              </pre>
            ) : null}
          </div>
        </div>
      </div>
    </dialog>
  );
}
