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
import { useLocale } from "../../lib/i18n/locale-context";
import { translate } from "../../lib/i18n/messages";
import { uiLang } from "../../lib/run-status";
import {
  normalizeReferenceType,
  referencesPayload,
  type ReferenceFile,
} from "../../lib/reference-types";

type Preview = { nodes: { id: string; title: string; agents: { agent: string; system: string; user: string }[] }[]; plan_present: boolean; plan_source?: string };

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
  const { t } = useLocale();
  const MODE_LABEL: Record<WorkMode, string> = {
    new: t("plan.modeNew"),
    revise: t("plan.modeRevise"),
  };
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
        if (!response.ok) throw new Error(data.detail || t("preview.orchFail"));
        const list = data.workflows || [];
        const wf = (workflowId && list.find((w) => w.id === workflowId)) || workflowForMode(list, mode);
        if (!wf) throw new Error(t("preview.noWorkflow"));
        if (cancelled) return;
        setWorkflow(wf);
        const pv = await apiFetch(`/api/workflow/preview?workflow=${encodeURIComponent(wf.id)}`);
        const pdata = (await pv.json()) as Preview & { detail?: string };
        if (!pv.ok) throw new Error(pdata.detail || t("preview.injectFail"));
        if (!cancelled) setPreview(pdata);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setWorkflowError(reason instanceof Error ? reason.message : t("preview.orchFail"));
      });
    return () => {
      cancelled = true;
    };
  }, [mode, workflowId, t]);

  const taskId = workflow?.id ?? "";
  const canStart = Boolean(workflow) && Boolean(taskId);
  const gateText =
    startError ||
    (workflowError ? t("preview.orchReadFail", { error: workflowError }) : "") ||
    (starting ? t("preview.startingOpen") : "");

  return (
    <div className="preview-board">
      <div className="preview-scroll">
        <section className="preview-section" aria-labelledby="preview-work-title">
          <h3 id="preview-work-title">{t("preview.workContent")}</h3>
          <dl className="preview-facts">
            {work.rows.map((row) => (
              <div key={row.id}>
                <dt>{row.label}</dt>
                <dd>{row.value || t("common.empty")}</dd>
              </div>
            ))}
          </dl>
        </section>

        {references.length ? (
          <section className="preview-section" aria-labelledby="preview-refs-title">
            <h3 id="preview-refs-title">{t("preview.refs")}</h3>
            <ul className="preview-ref-chips" data-testid="preview-ref-chips">
              {references.map((file) => (
                <li key={`${normalizeReferenceType(file.type)}:${file.name}`} className="preview-ref-chip" title={file.note?.trim() || undefined}>
                  <span className="preview-ref-kind">{t(`plan.refType.${normalizeReferenceType(file.type)}`)}</span>
                  <strong>{file.name}</strong>
                  <small>{formatSize(file.size)}</small>
                  {file.note?.trim() ? <span className="preview-ref-note">{file.note.trim()}</span> : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <section className="preview-section" aria-labelledby="preview-flow-title">
          <h3 id="preview-flow-title">{t("preview.workflow")}</h3>
          <p className="preview-flow-meta">
            {MODE_LABEL[mode]}
            {workflow ? ` · ${workflow.title || workflow.id} · ${workflow.plan_file}` : ""}
          </p>
          {workflowError ? <p className="status-banner error">{workflowError}</p> : null}
          {!workflow && !workflowError ? <p className="settings-help">{t("preview.loadingOrch")}</p> : null}
          {workflow ? (
            <ol className="preview-stages" data-testid="preview-stages">
              {workflow.details.map((node, index) => (
                <li key={node.id}>
                  <div className="preview-stage-head">
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{node.title || node.id}</strong>
                    <small>{t("preview.maxRounds", { n: node.max_rounds })}</small>
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
                        title={preview ? t("preview.viewInject") : undefined}
                      >
                        <Bot size={13} strokeWidth={1.75} aria-hidden="true" />
                        <em>{label(name)}</em>
                        <span>{agent.tools.mcp.length ? agent.tools.mcp.join(" · ") : agent.template || t("preview.inline")}</span>
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
            void executeTask(taskId, work.plan, references, setStarting, setStartError, (href) => router.push(href))
          }
        >
          <Play className="launch-icon" aria-hidden="true" />
          {starting ? t("preview.starting") : t("preview.execute")}
        </button>
      </div>
    </div>
  );
}

async function executeTask(
  task: string,
  fields: PlanFields,
  references: ReferenceFile[],
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
        template_id: fields.template_id,
        // StudyForm only keeps schema-legal items; never send dirty fragments.
        items: fields.items,
        references: referencesPayload(references),
      }),
    });
    if (!response.ok) {
      let detail = translate(uiLang(), "runs.startFailHttp", { status: response.status });
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
    setStartError(reason instanceof Error ? reason.message : translate(uiLang(), "preview.startFail"));
    setStarting(false);
  }
}
