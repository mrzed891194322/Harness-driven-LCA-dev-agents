"use client";

import { MarkdownView } from "../markdown-view";
import type { ResultFile } from "../../app/results/load-files";

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
    .replace(/^workspace\/records\/handoffs\//, "");
  const slash = trimmed.lastIndexOf("/");
  return slash >= 0 ? trimmed.slice(0, slash) : "";
}

type Props = {
  handoffs: Handoff[];
  artifacts: Artifact[];
  empty: boolean;
  selected: string;
  preview: Preview | null;
  fileError: string;
  formatSize: (bytes: number) => string;
  onOpen: (path: string) => void;
};

export function ArtifactsBrowser({
  handoffs,
  artifacts,
  empty,
  selected,
  preview,
  fileError,
  formatSize,
  onOpen,
}: Props) {
  return (
    <div className="results-columns">
      <nav className="results-pane results-nav" aria-label="文件">
        {empty ? <p className="settings-help">还没有文件。</p> : null}
        {handoffs.length ? (
          <section>
            <h3>工作记录</h3>
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
        {artifacts.length ? (
          <section>
            <h3>产物</h3>
            <ul>
              {artifacts.map((item) => (
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
          </section>
        ) : null}
      </nav>
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

export function firstArtifactPath(handoffs: Handoff[], artifacts: Artifact[]): string {
  if (handoffs[0]) return handoffPath(handoffs[0]);
  return artifacts[0]?.path || "";
}
