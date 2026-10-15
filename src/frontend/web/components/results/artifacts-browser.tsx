"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ResultFile } from "../../app/results/load-files";
import { MarkdownView } from "../markdown-view";

const MAX_ARTIFACT_ROWS = 200;

export type ResultKind = "work" | "intermediate" | "final";

const KIND_LABEL: Record<ResultKind, string> = {
  work: "工作记录",
  intermediate: "中间产物",
  final: "最终交付",
};

export function resultKind(
  filePath: string,
  category?: "intermediate" | "deliverable",
): ResultKind {
  if (category === "deliverable") return "final";
  if (category === "intermediate") return "intermediate";
  if (filePath.startsWith("workspace/artifacts/")) return "final";
  if (filePath.startsWith("workspace/runs/_run/")) return "work";
  if (filePath.startsWith("workspace/runs/")) return "intermediate";
  if (filePath.startsWith("workspace/records/")) return "work";
  if (filePath.startsWith("workspace/outputs/")) return "final";
  return "work";
}

export type Handoff = {
  name: string;
  stage: string;
  role: string;
  attempt: number | null;
  status: string;
  status_reason: string;
  artifacts: string[];
};

export type Artifact = {
  path: string;
  size: number;
  count?: number;
  category?: "intermediate" | "deliverable";
};

export type Preview =
  | ResultFile
  | { path: string; kind: "group"; size: number; text: ""; count: number };

const HANDOFF_STATUS: Record<string, string> = {
  ok: "完成",
  failed: "失败",
  blocked: "受阻",
  passed: "通过",
};

const ROLE_LABEL: Record<string, string> = {
  executor: "执行",
  reviser: "修订",
  reviewer: "审查",
};

function handoffPath(item: Handoff): string {
  if (item.name.includes("/")) {
    return `workspace/${item.name}`;
  }
  return `workspace/records/handoffs/${item.name}`;
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
    .replace(/^workspace\/outputs\//, "")
    .replace(/^workspace\/records\//, "")
    .replace(/^workspace\/runs\/_run\//, "");
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
                ? `${item.count} 个中间文件`
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
  const [kind, setKind] = useState<ResultKind>("final");
  const kindTouched = useRef(false);
  useEffect(() => {
    if (kindTouched.current || !selected) return;
    setKind(resultKind(selected));
  }, [selected]);

  const intermediate = useMemo(
    () =>
      artifacts.filter(
        (item) => resultKind(item.path, item.category) === "intermediate",
      ),
    [artifacts],
  );
  const finals = useMemo(
    () =>
      artifacts.filter((item) => resultKind(item.path, item.category) === "final"),
    [artifacts],
  );
  const visibleIntermediate = intermediate.slice(0, MAX_ARTIFACT_ROWS);
  const omittedIntermediate = Math.max(0, intermediate.length - visibleIntermediate.length);

  function chooseKind(next: ResultKind) {
    kindTouched.current = true;
    setKind(next);
  }

  return (
    <div className="results-columns">
      <div className="results-side">
        <div className="results-kind-tabs" role="tablist" aria-label="结果分类">
          {(Object.keys(KIND_LABEL) as ResultKind[]).map((item) => (
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
        <nav className="results-pane results-nav" aria-label="文件">
          {empty ? <p className="settings-help">还没有文件。</p> : null}
          {kind === "work" ? (
            <>
              {handoffs.length ? (
                <section>
                  <h3>交接</h3>
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
                            <strong>{item.stage || item.name}</strong>
                            <span>
                              {ROLE_LABEL[item.role] || item.role || "交接"}
                              {item.attempt != null ? ` · 第 ${item.attempt} 次` : ""}
                              {item.status ? ` · ${HANDOFF_STATUS[item.status] || item.status}` : ""}
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
                  <h3>其他记录</h3>
                  <FileList items={records} selected={selected} formatSize={formatSize} onOpen={onOpen} />
                </section>
              ) : null}
              {!handoffs.length && !records.length ? <p className="settings-help">还没有工作记录。</p> : null}
            </>
          ) : null}
          {kind === "intermediate" ? (
            intermediate.length ? (
              <>
                {omittedIntermediate ? (
                  <p className="settings-help">
                    仅显示前 {MAX_ARTIFACT_ROWS} 项，另有 {omittedIntermediate} 项未列出；请用下载产出或在磁盘浏览。
                  </p>
                ) : null}
                <FileList
                  items={visibleIntermediate}
                  selected={selected}
                  formatSize={formatSize}
                  onOpen={onOpen}
                />
              </>
            ) : (
              <p className="settings-help">还没有中间产物。这里列出 flow、process、product system 和计算调用记录。</p>
            )
          ) : null}
          {kind === "final" ? (
            finals.length ? (
              <FileList items={finals} selected={selected} formatSize={formatSize} onOpen={onOpen} />
            ) : (
              <p className="settings-help">还没有最终交付。报告、清单和计算计划会出现在这里。</p>
            )
          ) : null}
        </nav>
      </div>
      <section className="results-pane results-view" aria-label="文件内容">
        {preview ? (
          <>
            <header className="results-view-head">
              <strong className="results-path">{preview.path}</strong>
              {preview.kind !== "group" ? <span>{formatSize(preview.size)}</span> : null}
            </header>
            <div className="results-view-body">
              {preview.kind === "group" ? (
                <p className="settings-help">
                  这是中间调用记录，共 {preview.count} 个文件，{formatSize(preview.size)}。
                </p>
              ) : preview.kind === "too-large" ? (
                <p className="settings-help">文件较大（{formatSize(preview.size)}），这里不展开。</p>
              ) : preview.kind === "markdown" ? (
                <MarkdownView source={preview.text} />
              ) : preview.text ? (
                <pre className="results-source">
                  <code>{preview.text}</code>
                </pre>
              ) : (
                <p className="settings-help">文件是空的。</p>
              )}
            </div>
          </>
        ) : (
          <p className="settings-help">{fileError || "选择左侧文件查看内容。"}</p>
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
