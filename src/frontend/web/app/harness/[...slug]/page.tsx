"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { MarkdownView } from "../../../components/markdown-view";
import {
  HarnessShell,
  findHarnessEntry,
  harnessHref,
  type HarnessCatalog,
} from "../../../components/harness/harness-shell";
import { apiFetch } from "../../../lib/api";

type HarnessDocument = {
  path: string;
  label: string;
  title: string;
  kind: "markdown" | "yaml" | "json";
  content: string;
};

function slugToPath(slug: string[] | string | undefined) {
  const parts = Array.isArray(slug) ? slug : slug ? [slug] : [];
  return parts.map(decodeURIComponent).join("/");
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
  return parts.join("/") || null;
}

export default function HarnessDocPage() {
  const router = useRouter();
  const params = useParams<{ slug?: string[] }>();
  const selected = useMemo(() => slugToPath(params.slug), [params.slug]);
  const [catalog, setCatalog] = useState<HarnessCatalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [doc, setDoc] = useState<HarnessDocument | null>(null);
  const [documentError, setDocumentError] = useState("");
  const [loadingDoc, setLoadingDoc] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await apiFetch("/api/harness/catalog");
        const data = (await response.json()) as HarnessCatalog & { detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法加载 Harness 目录");
        if (!cancelled) {
          setCatalog(data);
          setCatalogError("");
        }
      } catch (err) {
        if (!cancelled) {
          setCatalogError(err instanceof Error ? err.message : "无法加载 Harness 目录");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    setLoadingDoc(true);
    setDocumentError("");
    (async () => {
      try {
        const response = await apiFetch(`/api/harness/document?path=${encodeURIComponent(selected)}`);
        const data = (await response.json()) as HarnessDocument & { detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法读取文档");
        if (!cancelled) setDoc(data);
      } catch (err) {
        if (!cancelled) {
          setDoc(null);
          setDocumentError(err instanceof Error ? err.message : "无法读取文档");
        }
      } finally {
        if (!cancelled) setLoadingDoc(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected]);

  function openRelative(href: string) {
    if (!selected || !catalog) return;
    const next = resolveRelative(selected, href);
    if (next && findHarnessEntry(catalog, next)) router.push(harnessHref(next));
  }

  return (
    <HarnessShell
      catalog={catalog}
      selected={selected}
      error={catalogError}
      title={doc?.path === selected ? doc.title : undefined}
      crumbPath={selected}
    >
      {catalogError ? <p className="harness-status">{catalogError}</p> : null}
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
    </HarnessShell>
  );
}
