"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { ResultFile } from "../../app/results/load-files";
import { MarkdownView } from "../markdown-view";
import { ChevronDown, ChevronRight, Folder, FolderOpen } from "lucide-react";

const MAX_ARTIFACT_ROWS = 200;

import { KIND_LABEL, RESULT_KINDS, resultKind, VERDICT_LABEL, type ArtifactCategory, type ResultKind } from "../../lib/result-kind";
import { useLocale } from "../../lib/i18n/locale-context";

export { resultKind, type ResultKind };

export type Handoff = {
  name: string;
  node: string;
  agent: string;
  attempt: number | null;
  status: string;
  status_reason: string;
  artifacts?: string[];
  node_status?: string;
};

export type Artifact = {
  path: string;
  size: number;
  count?: number;
  category?: ArtifactCategory;
};

export type Preview =
  | ResultFile
  | { path: string; kind: "group"; size: number; text: ""; count: number };

function handoffPath(item: Handoff): string {
  if (item.name.includes("/")) {
    return `workspace/${item.name}`;
  }
  return `workspace/runs/${item.name}`;
}

function baseName(filePath: string): string {
  const parts = filePath.split("/");
  return parts[parts.length - 1] || filePath;
}

/** Strip common workspace prefixes so the tree shows real dirs (e.g. evidence/<id>/). */
function treeRelPath(filePath: string): string {
  return filePath
    .replace(/^workspace\/artifacts\//, "")
    .replace(/^workspace\/runs\/_run\//, "")
    .replace(/^workspace\/runs\//, "")
    .replace(/^workspace\//, "");
}

type Props = {
  handoffs: Handoff[];
  artifacts: Artifact[];
  records: Artifact[];
  empty: boolean;
  selected: string;
  preview: Preview | null;
  fileError: string;
  formatSize: (bytes: number) => string;
  onOpen: (path: string) => void;
};

type TreeFile = { kind: "file"; name: string; item: Artifact };
type TreeDir = { kind: "dir"; name: string; path: string; children: TreeNode[] };
type TreeNode = TreeFile | TreeDir;

function insertPath(root: TreeDir, segments: string[], item: Artifact) {
  if (segments.length === 0) return;
  if (segments.length === 1) {
    root.children.push({ kind: "file", name: segments[0], item });
    return;
  }
  const [head, ...rest] = segments;
  let dir = root.children.find((child): child is TreeDir => child.kind === "dir" && child.name === head);
  if (!dir) {
    dir = { kind: "dir", name: head, path: root.path ? `${root.path}/${head}` : head, children: [] };
    root.children.push(dir);
  }
  insertPath(dir, rest, item);
}

function buildTree(items: Artifact[]): TreeNode[] {
  const root: TreeDir = { kind: "dir", name: "", path: "", children: [] };
  for (const item of items) {
    const rel = treeRelPath(item.path);
    const segments = rel.split("/").filter(Boolean);
    if (!segments.length) continue;
    insertPath(root, segments, item);
  }
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "dir" ? -1 : 1;
      return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    });
    for (const node of nodes) {
      if (node.kind === "dir") sortNodes(node.children);
    }
  };
  sortNodes(root.children);
  return root.children;
}

function FileTree({
  items,
  selected,
  formatSize,
  onOpen,
  defaultOpen = true,
}: {
  items: Artifact[];
  selected: string;
  formatSize: (bytes: number) => string;
  onOpen: (path: string) => void;
  defaultOpen?: boolean;
}) {
  const tree = useMemo(() => buildTree(items), [items]);
  const [openDirs, setOpenDirs] = useState<Record<string, boolean>>({});

  useEffect(() => {
    // Expand ancestors of the selected file so the active leaf is visible.
    if (!selected) return;
    const rel = treeRelPath(selected);
    const parts = rel.split("/").filter(Boolean);
    if (parts.length < 2) return;
    setOpenDirs((prev) => {
      const next = { ...prev };
      let acc = "";
      for (let i = 0; i < parts.length - 1; i += 1) {
        acc = acc ? `${acc}/${parts[i]}` : parts[i];
        next[acc] = true;
      }
      return next;
    });
  }, [selected]);

  function isOpen(path: string) {
    if (path in openDirs) return openDirs[path];
    return defaultOpen;
  }

  function toggle(path: string) {
    setOpenDirs((prev) => ({ ...prev, [path]: !isOpen(path) }));
  }

  function renderNodes(nodes: TreeNode[], depth: number): ReactNode {
    return (
      <ul className="results-tree" data-depth={depth}>
        {nodes.map((node) => {
          if (node.kind === "file") {
            const item = node.item;
            return (
              <li key={item.path} className="results-tree-file">
                <button
                  type="button"
                  style={{ paddingLeft: 8 + depth * 12 }}
                  aria-current={selected === item.path ? "page" : undefined}
                  onClick={() => onOpen(item.path)}
                >
                  <strong>{node.name}</strong>
                  <span>
                    {item.count && item.count > 1 ? String(item.count) : formatSize(item.size)}
                  </span>
                </button>
              </li>
            );
          }
          const open = isOpen(node.path);
          return (
            <li key={`dir:${node.path}`} className="results-tree-dir">
              <button
                type="button"
                className="results-tree-folder"
                style={{ paddingLeft: 8 + depth * 12 }}
                aria-expanded={open}
                onClick={() => toggle(node.path)}
              >
                {open ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
                {open ? <FolderOpen size={14} aria-hidden="true" /> : <Folder size={14} aria-hidden="true" />}
                <strong>{node.name}</strong>
                <span>{node.children.length}</span>
              </button>
              {open ? renderNodes(node.children, depth + 1) : null}
            </li>
          );
        })}
      </ul>
    );
  }

  if (!tree.length) return null;
  return renderNodes(tree, 0);
}

export function ArtifactsBrowser({
  handoffs,
  artifacts,
  records,
  empty,
  selected,
  preview,
  fileError,
  formatSize,
  onOpen,
}: Props) {
  const { t } = useLocale();
  const [kind, setKind] = useState<ResultKind>("final");
  const kindTouched = useRef(false);
  useEffect(() => {
    if (kindTouched.current || !selected) return;
    setKind(resultKind(selected));
  }, [selected]);

  const workFiles = useMemo(
    () =>
      artifacts.filter((item) => resultKind(item.path, item.category) === "work"),
    [artifacts],
  );
  const finals = useMemo(
    () =>
      artifacts.filter((item) => resultKind(item.path, item.category) === "final"),
    [artifacts],
  );
  const visibleWork = workFiles.slice(0, MAX_ARTIFACT_ROWS);
  const omittedWork = Math.max(0, workFiles.length - visibleWork.length);

  function chooseKind(next: ResultKind) {
    kindTouched.current = true;
    setKind(next);
  }

  return (
    <div className="results-columns">
      <div className="results-side">
        <div className="results-kind-tabs" role="tablist" aria-label={t("results.categories")}>
          {RESULT_KINDS.map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={kind === item}
              className={kind === item ? "is-active" : ""}
              onClick={() => chooseKind(item)}
            >
              {KIND_LABEL[item]}
            </button>
          ))}
        </div>
        <nav className="results-pane results-nav" aria-label={t("results.files")}>
          {empty ? <p className="settings-help">{t("results.noFiles")}</p> : null}
          {kind === "work" ? (
            <>
              {handoffs.length ? (
                <section>
                  <h3>{t("results.handoff")}</h3>
                  <ul>
                    {handoffs.map((item) => {
                      const filePath = handoffPath(item);
                      return (
                        <li key={filePath}>
                          <button
                            type="button"
                            aria-current={selected === filePath ? "page" : undefined}
                            onClick={() => onOpen(filePath)}
                          >
                            <strong>{item.node || item.name}
                              {item.node_status ? ` · ${VERDICT_LABEL[item.node_status] || item.node_status}` : ""}</strong>
                            <span>
                              {item.agent || t("results.handoff")}
                              {item.attempt != null ? t("results.attempt", { n: item.attempt }) : ""}
                              {item.status ? ` · ${VERDICT_LABEL[item.status] || item.status}` : ""}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null}
              {records.length ? (
                <section>
                  <h3>{t("results.otherRecords")}</h3>
                  <FileTree items={records} selected={selected} formatSize={formatSize} onOpen={onOpen} />
                </section>
              ) : null}
              {workFiles.length ? (
                <section>
                  <h3>{t("results.processFiles")}</h3>
                  {omittedWork ? (
                    <p className="settings-help">
                      {t("results.omitHint", { max: MAX_ARTIFACT_ROWS, n: omittedWork })}
                    </p>
                  ) : null}
                  <FileTree
                    items={visibleWork}
                    selected={selected}
                    formatSize={formatSize}
                    onOpen={onOpen}
                  />
                </section>
              ) : null}
              {!handoffs.length && !records.length && !workFiles.length ? (
                <p className="settings-help">{t("results.noWorkLog")}</p>
              ) : null}
            </>
          ) : null}
          {kind === "final" ? (
            finals.length ? (
              <FileTree items={finals} selected={selected} formatSize={formatSize} onOpen={onOpen} />
            ) : (
              <p className="settings-help">{t("results.noFinal")}</p>
            )
          ) : null}
        </nav>
      </div>
      <section className="results-pane results-view" aria-label={t("results.fileContent")}>
        {preview ? (
          <>
            <header className="results-view-head">
              <strong className="results-path">{preview.path}</strong>
              {preview.kind !== "group" ? <span>{formatSize(preview.size)}</span> : null}
            </header>
            <div className="results-view-body">
              {preview.kind === "group" ? (
                <p className="settings-help">
                  {t("results.midGroup", { count: preview.count, size: formatSize(preview.size) })}
                </p>
              ) : preview.kind === "too-large" ? (
                <p className="settings-help">{t("results.fileTooLarge", { size: formatSize(preview.size) })}</p>
              ) : preview.kind === "markdown" ? (
                <MarkdownView source={preview.text} />
              ) : preview.text ? (
                <pre className="results-source">
                  <code>{preview.text}</code>
                </pre>
              ) : (
                <p className="settings-help">{t("results.fileEmpty")}</p>
              )}
            </div>
          </>
        ) : (
          <p className="settings-help">{fileError || t("results.selectFile")}</p>
        )}
      </section>
    </div>
  );
}

export function firstArtifactPath(
  handoffs: Handoff[],
  artifacts: Artifact[],
  records: Artifact[] = [],
): string {
  const finalPath = artifacts.find(
    (item) => resultKind(item.path, item.category) === "final",
  )?.path;
  if (finalPath) return finalPath;
  if (handoffs[0]) return handoffPath(handoffs[0]);
  return artifacts[0]?.path || records[0]?.path || "";
}
