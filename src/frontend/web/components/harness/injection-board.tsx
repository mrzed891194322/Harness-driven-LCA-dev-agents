"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";
import {
  fetchWorkflowList,
  fetchWorkflowManifest,
  stageTitle,
  type WorkflowListItem,
  type WorkflowManifest,
} from "../../lib/workflow-manifest";

type InjectionNode = {
  stage_id: string;
  assignment_id: string;
  role: string;
};

type InjectionRow = {
  id: string;
  layer: string;
  locked: boolean;
  removed: boolean;
};

type InjectionDetail = {
  workflow: string;
  stage_id?: string;
  assignment_id?: string;
  rules?: InjectionRow[];
  mcp?: InjectionRow[];
  knowledge?: InjectionRow[];
  permissions?: Record<string, unknown>;
  planned?: {
    system_prompt_hash?: string;
  };
  compose_notes?: string[];
};

type PlannedBuild = {
  system_prompt_hash?: string;
};

function layerBadge(layer: string) {
  return <span className="injection-layer">{layer}</span>;
}

function RowList({
  title,
  rows,
  onOpenRule,
}: {
  title: string;
  rows: InjectionRow[];
  onOpenRule: (id: string) => void;
}) {
  if (!rows.length) return null;
  return (
    <section className="injection-group">
      <h3>{title}</h3>
      <ul className="injection-rows">
        {rows.map((row) => (
          <li key={row.id} data-locked={row.locked ? "true" : undefined}>
            {title === "规则" ? (
              <button type="button" className="injection-rule-link" onClick={() => onOpenRule(row.id)}>
                {row.id}
              </button>
            ) : (
              <span className="mono">{row.id}</span>
            )}
            {layerBadge(row.layer)}
            {row.locked ? <span title="锁定">🔒</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function InjectionBoard() {
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
  const [workflowName, setWorkflowName] = useState("");
  const [manifest, setManifest] = useState<WorkflowManifest | null>(null);
  const [nodes, setNodes] = useState<InjectionNode[]>([]);
  const [selected, setSelected] = useState<InjectionNode | null>(null);
  const [detail, setDetail] = useState<InjectionDetail | null>(null);
  const [plannedHash, setPlannedHash] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchWorkflowList()
      .then((list) => {
        setWorkflows(list);
        if (!list.length) return;
        const preferred = list.find((item) => item.mode === "main") ?? list[0];
        setWorkflowName((current) =>
          current && list.some((item) => item.name === current) ? current : preferred.name,
        );
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "无法读取工作流");
      });
  }, []);

  useEffect(() => {
    if (!workflowName) return;
    let cancelled = false;
    fetchWorkflowManifest(workflowName)
      .then((data) => {
        if (!cancelled) setManifest(data);
      })
      .catch(() => {
        if (!cancelled) setManifest(null);
      });
    return () => {
      cancelled = true;
    };
  }, [workflowName]);

  useEffect(() => {
    if (!workflowName) return;
    let cancelled = false;
    apiFetch(`/api/harness/injection?workflow=${encodeURIComponent(workflowName)}`)
      .then(async (response) => {
        const data = (await response.json()) as { nodes?: InjectionNode[]; detail?: unknown };
        if (!response.ok) {
          const detailText =
            typeof data.detail === "string"
              ? data.detail
              : JSON.stringify(data.detail ?? "无法读取注入树");
          throw new Error(detailText);
        }
        if (!cancelled) {
          setNodes(data.nodes ?? []);
          setSelected(null);
          setDetail(null);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "无法读取注入树");
      });
    return () => {
      cancelled = true;
    };
  }, [workflowName]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      setPlannedHash("");
      return;
    }
    let cancelled = false;
    const query = new URLSearchParams({
      workflow: workflowName,
      stage: selected.stage_id,
      assignment: selected.assignment_id,
    });
    apiFetch(`/api/harness/injection?${query.toString()}`)
      .then(async (response) => {
        const data = (await response.json()) as InjectionDetail & { detail?: unknown };
        if (!response.ok) throw new Error(String(data.detail ?? "无法读取注入"));
        if (cancelled) return;
        setDetail(data);
        const planned = data.planned as PlannedBuild | undefined;
        setPlannedHash(planned?.system_prompt_hash ?? "");
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "无法读取注入");
      });
    return () => {
      cancelled = true;
    };
  }, [selected, workflowName]);

  const tree = useMemo(() => {
    const byStage = new Map<string, InjectionNode[]>();
    for (const node of nodes) {
      const list = byStage.get(node.stage_id) ?? [];
      list.push(node);
      byStage.set(node.stage_id, list);
    }
    return byStage;
  }, [nodes]);

  function openRule(ruleId: string) {
    window.open(`/harness/rules/${encodeURIComponent(ruleId)}.md`, "_blank", "noopener");
  }

  return (
    <div className="injection-board">
      <div className="injection-toolbar">
        <label>
          工作流
          <select
            value={workflowName}
            onChange={(event) => {
              setError("");
              setWorkflowName(event.target.value);
            }}
          >
            {workflows.map((item) => (
              <option key={item.name} value={item.name}>
                {item.title || item.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error ? <p className="harness-status">{error}</p> : null}
      <div className="injection-split">
        <nav className="injection-tree" aria-label="阶段与分工">
          {[...tree.entries()].map(([stageId, items]) => (
            <div key={stageId} className="injection-stage">
              <p className="injection-stage-title">{stageTitle(manifest, stageId)}</p>
              <ul>
                {items.map((node) => (
                  <li key={node.assignment_id}>
                    <button
                      type="button"
                      aria-current={selected?.assignment_id === node.assignment_id ? "true" : undefined}
                      onClick={() => {
                        setError("");
                        setSelected(node);
                      }}
                    >
                      {node.assignment_id}
                      <span className="injection-role">{node.role}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="injection-detail">
          {!selected ? (
            <p className="harness-status">选择左侧分工查看组合注入（只读）。</p>
          ) : (
            <>
              <header className="injection-detail-head">
                <h3>{selected.assignment_id}</h3>
                {plannedHash ? (
                  <p className="mono harness-path">system_prompt_hash: {plannedHash}</p>
                ) : null}
              </header>
              <RowList title="规则" rows={detail?.rules ?? []} onOpenRule={openRule} />
              <RowList title="MCP" rows={detail?.mcp ?? []} onOpenRule={openRule} />
              <RowList title="知识" rows={detail?.knowledge ?? []} onOpenRule={openRule} />
              {detail?.permissions ? (
                <section className="injection-group">
                  <h3>权限</h3>
                  <pre className="harness-source">
                    <code>{JSON.stringify(detail.permissions, null, 2)}</code>
                  </pre>
                </section>
              ) : null}
              {detail?.planned ? (
                <section className="injection-group">
                  <h3>生成提示</h3>
                  <p className="settings-help">
                    完整 planned 载荷由后端 <code>build_intended</code> 生成（只读预览）。
                  </p>
                </section>
              ) : null}
              {detail?.compose_notes?.length ? (
                <section className="injection-group">
                  <h3>合并说明</h3>
                  <ul>
                    {detail.compose_notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </section>
              ) : null}
              <p className="settings-help">
                规则原文：
                <Link href="/harness/rules/project/runtime.md">Harness 文档浏览器</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
