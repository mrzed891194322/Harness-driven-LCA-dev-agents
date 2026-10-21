"use client";

// Restored from master 599ed0a (same layout and CSS). v5 data: /api/v5/workflows for the flow,
// /api/v5/preview for each agent's exact injection (read-only), start via /api/workflow/start as on /runs.
import { Bot, Play, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { WorkMode } from "./workflow-board";
import type { PlanFields } from "./plan-fields";
import type { StudyWork } from "./study-form";
import { apiFetch } from "../../lib/api";
import { label } from "../../lib/labels";
import { workflowForMode, type V5Workflow } from "../../lib/v5-workflow";

type Preview = { nodes: { id: string; title: string; agents: { role: string; system: string; user: string }[] }[]; plan_present: boolean; plan_source?: string };

type ReferenceFile = {
  name: string;
  size: number;
  note?: string;
};

type Check = { ok: boolean; message: string };

type Diagnostics = {
  pi_agents: Check;
  python_agent: Check;
  openlca: Check;
  node?: Check;
  model?: {
    profile_id?: string;
    display_name?: string;
    model_id?: string;
    credential_set?: boolean;
  };
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

function isDiagnostics(value: unknown): value is Diagnostics {
  if (!value || typeof value !== "object") return false;
  const row = value as Diagnostics;
  return Boolean(row.pi_agents && row.python_agent && row.openlca && "ok" in row.pi_agents);
}

export function PreviewBoard({
  mode,
  work,
  references,
}: {
  mode: WorkMode;
  work: StudyWork;
  references: ReferenceFile[];
}) {
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [envError, setEnvError] = useState("");
  const [checking, setChecking] = useState(true);
  const [workflow, setWorkflow] = useState<V5Workflow | null>(null);
  const [workflowError, setWorkflowError] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [open, setOpen] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    setChecking(true);
    setEnvError("");
    apiFetch("/api/diagnostics/environment")
      .then(async (response) => {
        const data = (await response.json()) as unknown;
        if (!response.ok || !isDiagnostics(data)) {
          throw new Error(`环境诊断不可用（HTTP ${response.status}）`);
        }
        return data;
      })
      .then((data) => {
        if (cancelled) return;
        setDiag(data);
        setChecking(false);
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setDiag(null);
        setChecking(false);
        setEnvError(reason instanceof Error ? reason.message : "环境诊断不可用");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setWorkflow(null);
    setPreview(null);
    setWorkflowError("");
    apiFetch("/api/v5/workflows")
      .then(async (response) => {
        const data = (await response.json()) as { workflows?: V5Workflow[]; detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法读取编排");
        const wf = workflowForMode(data.workflows || [], mode);
        if (!wf) throw new Error("没有对应的工作流");
        if (cancelled) return;
        setWorkflow(wf);
        const pv = await apiFetch(`/api/v5/preview?workflow=${encodeURIComponent(wf.id)}`);
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
  }, [mode]);

  const checks = environmentChecks(diag);
  const shownChecks = checks.filter((item) => item.label !== "模型");
  const envReady = Boolean(diag) && checks.every((item) => item.ok);
  const missingFields = work.rows.flatMap((row) => row.gaps);
  const taskId = workflow?.id ?? "";
  const ready =
    envReady && missingFields.length === 0 && !envError && Boolean(workflow) && Boolean(taskId);
  const gateText =
    startError ||
    (workflowError ? `编排读取失败：${workflowError}` : "") ||
    gateMessage({ checking, envError, checks, missingFields, ready, starting });

  return (
    <div className="preview-board">
      <div className="preview-scroll">
        <section className="preview-section" aria-labelledby="preview-env-title">
          <h3 id="preview-env-title">环境</h3>
          {envError ? <p className="status-banner error">{envError}</p> : null}
          {!diag && !envError ? <p className="settings-help">正在检查环境…</p> : null}
          {shownChecks.length ? (
            <ul className="diag-list preview-checks">
              {shownChecks.map((item) => (
                <li key={item.label}>
                  <span className={`badge ${item.ok ? "badge-ok" : "badge-warn"}`}>{item.ok ? "就绪" : "未就绪"}</span>
                  <span>
                    {item.label}：{item.message}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        <section className="preview-section" aria-labelledby="preview-work-title">
          <h3 id="preview-work-title">工作内容</h3>
          <dl className="preview-facts">
            {work.rows.map((row) => (
              <div key={row.id}>
                <dt>
                  {row.label}
                  {row.required && row.gaps.length > 0 ? <span className="badge badge-warn">待填写</span> : null}
                </dt>
                <dd>{row.value || (row.required ? "这一项还空着" : "留空")}</dd>
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
                      <li key={name} data-role={agent.role}>
                        <Bot size={13} strokeWidth={1.75} aria-hidden="true" />
                        <em>{label(name)}</em>
                        <span>{agent.tools.mcp.length ? agent.tools.mcp.join(" · ") : agent.role}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          ) : null}
        </section>

      </div>
      <div className="preview-bar">
        <p>{gateText}</p>
        <button
          type="button"
          className="primary"
          data-testid="preview-start"
          disabled={!ready || starting}
          onClick={() =>
            void executeTask(taskId, work.plan, setStarting, setStartError, (href) => router.push(href))
          }
        >
          <Play className="launch-icon" aria-hidden="true" />
          {starting ? "正在启动…" : "执行LCA任务"}
        </button>
        <button
          type="button"
          onClick={() => void reloadEnvironment(setChecking, setEnvError, setDiag)}
          disabled={checking}
        >
          <RefreshCw className="launch-icon" aria-hidden="true" />
          {checking ? "刷新中…" : "刷新状态"}
        </button>
      </div>
    </div>
  );
}

function environmentChecks(diag: Diagnostics | null): { label: string; ok: boolean; message: string }[] {
  if (!diag) return [];
  const model = diag.model;
  const modelOk = Boolean(model?.credential_set);
  const modelName = model?.display_name || model?.profile_id || "";
  return [
    {
      label: "Pi",
      ok: diag.pi_agents.ok,
      message: diag.pi_agents.ok ? diag.node?.message || diag.pi_agents.message : diag.pi_agents.message,
    },
    { label: "Python", ok: diag.python_agent.ok, message: diag.python_agent.message },
    { label: "openLCA", ok: diag.openlca.ok, message: diag.openlca.message },
    {
      label: "模型",
      ok: modelOk,
      message: modelOk
        ? modelName || "已连接"
        : modelName
          ? `${modelName} 还没有凭证`
          : "还没有可用模型",
    },
  ];
}

function gateMessage({
  checking,
  envError,
  checks,
  missingFields,
  ready,
  starting,
}: {
  checking: boolean;
  envError: string;
  checks: { label: string; ok: boolean }[];
  missingFields: string[];
  ready: boolean;
  starting: boolean;
}): string {
  if (starting) return "正在启动，即将打开运行详情…";
  if (checking && !checks.length) return "正在检查环境…";
  if (ready) return "环境和工作内容已齐，可以执行";
  const parts: string[] = [];
  if (envError) parts.push(envError);
  else {
    const blocked = checks.filter((item) => !item.ok).map((item) => item.label);
    if (blocked.length) parts.push(`环境未就绪：${blocked.join("、")}`);
  }
  if (missingFields.length) parts.push(`还要填写：${missingFields.join("、")}`);
  return parts.join("。") || "还不能执行";
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

async function reloadEnvironment(
  setChecking: (value: boolean) => void,
  setEnvError: (value: string) => void,
  setDiag: (value: Diagnostics | null) => void,
) {
  setChecking(true);
  setEnvError("");
  try {
    const response = await apiFetch("/api/diagnostics/environment");
    const data = (await response.json()) as unknown;
    if (!response.ok || !isDiagnostics(data)) {
      throw new Error(`环境诊断不可用（HTTP ${response.status}）`);
    }
    setDiag(data);
  } catch (reason: unknown) {
    setDiag(null);
    setEnvError(reason instanceof Error ? reason.message : "环境诊断不可用");
  } finally {
    setChecking(false);
  }
}
