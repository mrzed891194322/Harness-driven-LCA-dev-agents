"use client";

import { Play, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { readWorkflow, type WorkflowGraph } from "./workflow-yaml";
import type { WorkMode } from "./workflow-board";

type PlanFields = {
  subject: string;
  functional_unit: string;
  life_cycle_stages: string;
  conditions: string;
};

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

const MODE_FILE: Record<WorkMode, string> = {
  new: "LCA-main.yaml",
  revise: "LCA-revise.yaml",
};

const MODE_LABEL: Record<WorkMode, string> = {
  new: "新工作",
  revise: "修改工作",
};

const FILE_LABEL: Record<string, string> = {
  "LCA-main.yaml": "主流程",
  "LCA-revise.yaml": "修订流程",
};

const STAGE_TITLE: Record<string, string> = {
  "01-intake-gate": "初始化检查",
  "02-inventory-extraction": "前景清单",
  "03-dataset-mapping": "数据集映射",
  "04-openlca-reporting": "计算与报告",
};

const ROLE_LABEL: Record<string, string> = {
  executor: "执行",
  reviewer: "审阅",
  reviser: "修订",
};

const PHASE_LABEL: Record<string, string> = {
  inventory: "清单",
  mapping: "映射",
  report: "报告",
};

const requiredFields: { key: keyof PlanFields; label: string }[] = [
  { key: "subject", label: "研究对象" },
  { key: "functional_unit", label: "功能单位" },
  { key: "life_cycle_stages", label: "生命周期阶段" },
];

const contentFields: { key: keyof PlanFields; label: string }[] = [
  ...requiredFields,
  { key: "conditions", label: "附加条件" },
];

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
  fields,
  references,
}: {
  mode: WorkMode;
  fields: PlanFields;
  references: ReferenceFile[];
}) {
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [envError, setEnvError] = useState("");
  const [checking, setChecking] = useState(true);
  const [workflow, setWorkflow] = useState<WorkflowGraph | null>(null);
  const [workflowError, setWorkflowError] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    setChecking(true);
    setEnvError("");
    fetch("/api/diagnostics/environment")
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
    const file = MODE_FILE[mode];
    let cancelled = false;
    setWorkflow(null);
    setWorkflowError("");
    fetch(`/api/harness/document?path=${encodeURIComponent(file)}`)
      .then(async (response) => {
        const data = (await response.json()) as { content?: string; detail?: string };
        if (!response.ok || !data.content) throw new Error(data.detail || "无法读取编排");
        return readWorkflow(data.content, file);
      })
      .then((graph) => {
        if (!cancelled) setWorkflow(graph);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setWorkflowError(reason instanceof Error ? reason.message : "无法读取编排");
      });
    return () => {
      cancelled = true;
    };
  }, [mode]);

  const shown = workflow?.file === MODE_FILE[mode] ? workflow : null;
  const checks = environmentChecks(diag);
  const envReady = Boolean(diag) && checks.every((item) => item.ok);
  const missingFields = requiredFields.filter((item) => !fields[item.key].trim());
  const ready = envReady && missingFields.length === 0 && !envError;
  const gateText = startError || gateMessage({ checking, envError, checks, missingFields, ready, starting });

  return (
    <div className="preview-board">
      <div className="preview-scroll">
        <section className="preview-section" aria-labelledby="preview-env-title">
          <h3 id="preview-env-title">环境</h3>
          {envError ? <p className="status-banner error">{envError}</p> : null}
          {!diag && !envError ? <p className="settings-help">正在检查环境…</p> : null}
          {checks.length ? (
            <ul className="diag-list preview-checks">
              {checks.map((item) => (
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
            {contentFields.map((item) => {
              const value = fields[item.key].trim();
              const required = requiredFields.some((field) => field.key === item.key);
              return (
                <div key={item.key}>
                  <dt>
                    {item.label}
                    {required && !value ? <span className="badge badge-warn">待填写</span> : null}
                  </dt>
                  <dd>{value || (required ? "这一项还空着" : "留空")}</dd>
                </div>
              );
            })}
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
            {MODE_LABEL[mode]} · {FILE_LABEL[MODE_FILE[mode]]} · {MODE_FILE[mode]}
            {shown ? ` · ${shown.id} · 最多 ${shown.maxAttempts} 次` : ""}
          </p>
          {workflowError ? <p className="status-banner error">{workflowError}</p> : null}
          {!shown && !workflowError ? <p className="settings-help">正在读取编排…</p> : null}
          {shown ? (
            <ol className="preview-stages">
              {shown.stages.map((stage) => (
                <li key={stage.id}>
                  <div className="preview-stage-head">
                    <span>{stage.id.slice(0, 2)}</span>
                    <strong>{STAGE_TITLE[stage.id] ?? stage.id}</strong>
                    <small>
                      最多 {stage.maxAttempts} 次
                      {stage.phase ? ` · ${PHASE_LABEL[stage.phase] ?? stage.phase}` : ""}
                    </small>
                  </div>
                  <ul>
                    {stage.steps.map((step) => {
                      const assignment = shown.assignments.find((item) => item.id === step.assignment);
                      const role = assignment?.role ?? "";
                      return (
                        <li key={step.assignment} data-role={role}>
                          <em>{ROLE_LABEL[role] ?? role}</em>
                          <span>{assignment?.mcp.length ? assignment.mcp.join(" · ") : role}</span>
                        </li>
                      );
                    })}
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
          disabled={!ready || starting}
          onClick={() =>
            void executeTask(mode, fields, setStarting, setStartError, (href) => router.push(href))
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
  missingFields: { label: string }[];
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
  if (missingFields.length) parts.push(`还要填写：${missingFields.map((item) => item.label).join("、")}`);
  return parts.join("。") || "还不能执行";
}

async function executeTask(
  mode: WorkMode,
  fields: PlanFields,
  setStarting: (value: boolean) => void,
  setStartError: (value: string) => void,
  push: (href: string) => void,
) {
  setStarting(true);
  setStartError("");
  try {
    const response = await fetch("/api/workflow/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task: mode === "revise" ? "revise-lca" : "whole-lca",
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
    push("/runs");
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
    const response = await fetch("/api/diagnostics/environment");
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
