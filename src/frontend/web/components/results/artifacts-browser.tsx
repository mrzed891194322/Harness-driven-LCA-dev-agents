"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ResultFile } from "../../app/results/load-files";
import { MarkdownView } from "../markdown-view";

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

function navTitle(item: Artifact): string {
  if ((item.count || 1) > 1) {
    const parts = item.path.split("/");
    return parts.slice(-2).join("/");
  }
  return baseName(item.path);
}

function parentName(filePath: string): string {
  const trimmed = filePath
    .replace(/^workspace\/artifacts\//, "")
    .replace(/^workspace\/runs\/_run\//, "")
    .replace(/^workspace\/runs\//, "");
  const slash = trimmed.lastIndexOf("/");
  return slash >= 0 ? trimmed.slice(0, slash) : "";
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

function FileList({
  items,
  selected,
  formatSize,
  onOpen,
}: {
  items: Artifact[];
  selected: string;
  formatSize: (bytes: number) => string;
  onOpen: (path: string) => void;
}) {
  const { t } = useLocale();
  return (
    <ul>
      {items.map((item) => (
        <li key={item.path}>
          <button
            type="button"
            aria-current={selected === item.path ? "page" : undefined}
            onClick={() => onOpen(item.path)}
          >
            <strong>{navTitle(item)}</strong>
            <span>
              {item.count && item.count > 1
                ? t("results.midFiles", { count: item.count })
                : parentName(item.path) || formatSize(item.size)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
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
                  <FileList items={records} selected={selected} formatSize={formatSize} onOpen={onOpen} />
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
                  <FileList
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
              <FileList items={finals} selected={selected} formatSize={formatSize} onOpen={onOpen} />
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
