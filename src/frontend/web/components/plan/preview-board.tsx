"use client";

// Restored from master 599ed0a (same layout and CSS). v5 data: /api/workflow/workflows for the flow,
// /api/workflow/preview for each agent's exact injection (read-only), start via /api/workflow/start as on /runs.
import { Bot, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { WorkMode } from "./workflow-board";
import type { PlanFields } from "./plan-fields";
import type { StudyWork } from "./study-form";
import { apiFetch } from "../../lib/api";
import { label } from "../../lib/labels";
import { PromptModal, type PreviewAgent } from "./injection-preview";
import { workflowForMode, type WorkflowCard } from "../../lib/workflow-cards";

type Preview = { nodes: { id: string; title: string; agents: { agent: string; system: string; user: string }[] }[]; plan_present: boolean; plan_source?: string };

type ReferenceFile = {
  name: string;
  size: number;
  note?: string;
};

const MODE_LABEL: Record<WorkMode, string> = {
  new: "新工作",
  revise: "修改工作",
};


function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function PreviewBoard({
  mode,
  work,
  references,
  workflowId = null,
}: {
  mode: WorkMode;
  work: StudyWork;
  references: ReferenceFile[];
  /** Preset picked on 工作流编排; null = mode default (full-lca / revise-lca). */
  workflowId?: string | null;
}) {
  const [workflow, setWorkflow] = useState<WorkflowCard | null>(null);
  const [workflowError, setWorkflowError] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [open, setOpen] = useState<{ node: { id: string; title: string }; agent: PreviewAgent } | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    setWorkflow(null);
    setPreview(null);
    setWorkflowError("");
    apiFetch("/api/workflow/workflows")
      .then(async (response) => {
        const data = (await response.json()) as { workflows?: WorkflowCard[]; detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法读取编排");
        const list = data.workflows || [];
        const wf = (workflowId && list.find((w) => w.id === workflowId)) || workflowForMode(list, mode);
        if (!wf) throw new Error("没有对应的工作流");
        if (cancelled) return;
        setWorkflow(wf);
        const pv = await apiFetch(`/api/workflow/preview?workflow=${encodeURIComponent(wf.id)}`);
        const pdata = (await pv.json()) as Preview & { detail?: string };
        if (!pv.ok) throw new Error(pdata.detail || "无法生成注入预览");
        if (!cancelled) setPreview(pdata);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setWorkflowError(reason instanceof Error ? reason.message : "无法读取编排");
      });
    return () => {
      cancelled = true;
    };
  }, [mode, workflowId]);

  const taskId = workflow?.id ?? "";
  const canStart = Boolean(workflow) && Boolean(taskId);
  const gateText =
    startError ||
    (workflowError ? `编排读取失败：${workflowError}` : "") ||
    (starting ? "正在启动，即将打开运行详情…" : "");

  return (
    <div className="preview-board">
      <div className="preview-scroll">
        <section className="preview-section" aria-labelledby="preview-work-title">
          <h3 id="preview-work-title">工作内容</h3>
          <dl className="preview-facts">
            {work.rows.map((row) => (
              <div key={row.id}>
                <dt>{row.label}</dt>
                <dd>{row.value || "留空"}</dd>
              </div>
            ))}
          </dl>
          <h4>参考资料</h4>
          {references.length ? (
            <ul className="preview-files">
              {references.map((file) => (
                <li key={file.name}>
                  <strong>{file.name}</strong>
                  <small>{formatSize(file.size)}</small>
                  {file.note?.trim() ? <p>{file.note.trim()}</p> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="settings-meta">还没有参考资料。</p>
          )}
        </section>

        <section className="preview-section" aria-labelledby="preview-flow-title">
          <h3 id="preview-flow-title">工作流</h3>
          <p className="preview-flow-meta">
            {MODE_LABEL[mode]}
            {workflow ? ` · ${workflow.title || workflow.id} · ${workflow.plan_file}` : ""}
          </p>
          {workflowError ? <p className="status-banner error">{workflowError}</p> : null}
          {!workflow && !workflowError ? <p className="settings-help">正在读取编排…</p> : null}
          {workflow ? (
            <ol className="preview-stages" data-testid="preview-stages">
              {workflow.details.map((node, index) => (
                <li key={node.id}>
                  <div className="preview-stage-head">
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{node.title || node.id}</strong>
                    <small>最多 {node.max_rounds} 轮</small>
                  </div>
                  <ul>
                    {Object.entries(node.agents).map(([name, agent]) => (
                      <li
                        key={name}
                        data-agent={name}
                        data-testid={`preview-agent-${node.id}.${name}`}
                        onClick={() => {
                          const hit = preview?.nodes.find((n) => n.id === node.id)?.agents.find((x) => x.agent === name);
                          if (hit) setOpen({ node: { id: node.id, title: node.title }, agent: hit });
                        }}
                        title={preview ? "查看组合注入" : undefined}
                      >
                        <Bot size={13} strokeWidth={1.75} aria-hidden="true" />
                        <em>{label(name)}</em>
                        <span>{agent.tools.mcp.length ? agent.tools.mcp.join(" · ") : agent.template || "内联"}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          ) : null}
        </section>


      </div>
      <PromptModal node={open?.node ?? null} agent={open?.agent ?? null} onClose={() => setOpen(null)} />
      <div className="preview-bar">
        {gateText ? <p>{gateText}</p> : null}
        <button
          type="button"
          className="primary"
          data-testid="preview-start"
          disabled={!canStart || starting}
          onClick={() =>
            void executeTask(taskId, work.plan, setStarting, setStartError, (href) => router.push(href))
          }
        >
          <Play className="launch-icon" aria-hidden="true" />
          {starting ? "正在启动…" : "执行LCA任务"}
        </button>
      </div>
    </div>
  );
}

async function executeTask(
  task: string,
  fields: PlanFields,
  setStarting: (value: boolean) => void,
  setStartError: (value: string) => void,
  push: (href: string) => void,
) {
  setStarting(true);
  setStartError("");
  try {
    const response = await apiFetch("/api/workflow/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workflow: task,
        subject: fields.subject,
        functional_unit: fields.functional_unit,
        life_cycle_stages: fields.life_cycle_stages,
        conditions: fields.conditions,
      }),
    });
    if (!response.ok) {
      let detail = `无法启动（HTTP ${response.status}）`;
      try {
        const data = (await response.json()) as { detail?: string };
        if (data.detail) detail = data.detail;
      } catch {
        // Response body is not JSON.
      }
      throw new Error(detail);
    }
    push(`/runs?workflow=${encodeURIComponent(task)}`);
  } catch (reason: unknown) {
    setStartError(reason instanceof Error ? reason.message : "无法启动工作流");
    setStarting(false);
  }
}
