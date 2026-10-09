"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { MarkdownView } from "../../../components/markdown-view";
import {
  TutorialShell,
  type TutorialCatalog,
  type TutorialDocument,
} from "../../../components/tutorial/tutorial-shell";

function slugToPath(slug: string[] | string | undefined) {
  const parts = Array.isArray(slug) ? slug : slug ? [slug] : [];
  if (!parts.length) return "";
  const joined = parts.map(decodeURIComponent).join("/");
  return joined.toLowerCase().endsWith(".md") ? joined : `${joined}.md`;
}

function resolveTutorialAsset(docPath: string, href: string) {
  const clean = href.split("#")[0].split("?")[0].trim();
  if (!clean) return null;
  const baseParts = docPath.split("/").slice(0, -1);
  for (const part of clean.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") baseParts.pop();
    else baseParts.push(part);
  }
  const assetPath = baseParts.join("/");
  if (!assetPath || assetPath.startsWith("..")) return null;
  return `/api/tutorial/asset?path=${encodeURIComponent(assetPath)}`;
}

export default function TutorialDocPage() {
  const params = useParams<{ slug?: string[] }>();
  const selected = useMemo(() => slugToPath(params.slug), [params.slug]);
  const [catalog, setCatalog] = useState<TutorialCatalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [doc, setDoc] = useState<TutorialDocument | null>(null);
  const [documentError, setDocumentError] = useState("");
  const [loadingDoc, setLoadingDoc] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch("/api/tutorial/catalog");
        const data = (await response.json()) as TutorialCatalog & { detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法加载教程目录");
        if (!cancelled) {
          setCatalog(data);
          setCatalogError("");
        }
      } catch (err) {
        if (!cancelled) {
          setCatalogError(err instanceof Error ? err.message : "无法加载教程目录");
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
        const response = await fetch(
          `/api/tutorial/document?path=${encodeURIComponent(selected)}`,
        );
        const data = (await response.json()) as TutorialDocument & { detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法读取教程");
        if (!cancelled) setDoc(data);
      } catch (err) {
        if (!cancelled) {
          setDoc(null);
          setDocumentError(err instanceof Error ? err.message : "无法读取教程");
        }
      } finally {
        if (!cancelled) setLoadingDoc(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected]);

  return (
    <TutorialShell
      catalog={catalog}
      selected={selected}
      error={catalogError}
      title={doc?.path === selected ? doc.title : undefined}
      crumbPath={selected}
    >
      {catalogError ? <p className="harness-status">{catalogError}</p> : null}
      {documentError ? <p className="harness-status">{documentError}</p> : null}
      {loadingDoc && doc?.path !== selected ? <p className="harness-status">正在读取…</p> : null}
      {doc && doc.path === selected ? (
        <MarkdownView
          source={doc.content}
          resolveAsset={(href) => resolveTutorialAsset(selected, href)}
        />
      ) : null}
    </TutorialShell>
  );
}
