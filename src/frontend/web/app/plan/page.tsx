"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Download, FileText, MessageSquare, PenLine, Play, Trash2, Upload, Workflow } from "lucide-react";
import { PreviewBoard } from "../../components/plan/preview-board";
import { WorkflowBoard } from "../../components/plan/workflow-board";
import { apiFetch } from "../../lib/api";

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

const emptyFields: PlanFields = {
  subject: "",
  functional_unit: "",
  life_cycle_stages: "",
  conditions: "",
};

type Panel = "fields" | "references" | "workflow" | "preview";

const panels: { id: Panel; label: string }[] = [
  { id: "fields", label: "用户填写" },
  { id: "references", label: "参考资料" },
  { id: "workflow", label: "工作流编排" },
  { id: "preview", label: "预览执行" },
];

function PanelIcon({ id }: { id: Panel }) {
  const Icon = id === "fields" ? PenLine : id === "references" ? FileText : id === "workflow" ? Workflow : Play;
  return <Icon className="launch-icon" aria-hidden="true" />;
}

const fields: { key: keyof PlanFields; label: string; hint: string; placeholder: string }[] = [
  {
    key: "subject",
    label: "研究对象",
    hint: "比较对象、情景和交付地点",
    placeholder: "例如：比较三种供应路线下在德国销售点交付的 1 L PET 静水瓶",
  },
  {
    key: "functional_unit",
    label: "功能单位",
    hint: "功能描述、数量和单位",
    placeholder: "例如：在德国销售点交付 1,000 个装有 1 L 静水的 PET 瓶",
  },
  {
    key: "life_cycle_stages",
    label: "生命周期阶段",
    hint: "纳入和排除的阶段",
    placeholder: "例如：从原料到销售点，不包括使用、回收和最终处置",
  },
  {
    key: "conditions",
    label: "附加条件",
    hint: "研究目的、截断、分配、LCIA 方法、数据库和其他限制",
    placeholder: "没有额外限制时留空",
  },
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function duplicateReferenceNames(list: File[], existing: ReferenceFile[]): string[] {
  const taken = new Set(existing.map((file) => file.name));
  const conflicts: string[] = [];
  for (const file of list) {
    if (taken.has(file.name)) conflicts.push(file.name);
    else taken.add(file.name);
  }
  return [...new Set(conflicts)];
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string" && data.detail) return data.detail;
  } catch {
    // Response body is not JSON.
  }
  return `请求失败（${response.status}）`;
}

export default function PlanPage() {
  const [form, setForm] = useState<PlanFields>(emptyFields);
  const [references, setReferences] = useState<ReferenceFile[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [workMode, setWorkMode] = useState<"new" | "revise">("new");
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [panel, setPanel] = useState<Panel>("fields");
  const [noteTarget, setNoteTarget] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const planInput = useRef<HTMLInputElement>(null);
  const referenceInput = useRef<HTMLInputElement>(null);
  const noteDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    apiFetch("/api/plan")
      .then(async (response) => {
        if (!response.ok) throw new Error(await errorMessage(response));
        return response.json() as Promise<{ fields?: PlanFields; references?: ReferenceFile[] }>;
      })
      .then((data) => {
        setForm({ ...emptyFields, ...data.fields });
        setReferences(data.references ?? []);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "无法读取计划");
      });
  }, []);

  useEffect(() => {
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("mode") === "revise") {
      setWorkMode("revise");
    }
  }, []);

  useEffect(() => {
    const dialog = noteDialog.current;
    if (!dialog) return;
    if (noteTarget && !dialog.open) dialog.showModal();
    if (!noteTarget && dialog.open) dialog.close();
  }, [noteTarget]);

  function update(key: keyof PlanFields, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
    setStatus("");
  }

  async function downloadTemplate() {
    setError("");
    try {
      const response = await apiFetch("/api/plan/template");
      if (!response.ok) throw new Error(await errorMessage(response));
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "lca-plan-template.md";
      link.click();
      URL.revokeObjectURL(url);
      setStatus("已下载模板");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "模板下载失败");
    }
  }

  async function importPlan(file: File) {
    setError("");
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await apiFetch("/api/plan/import", { method: "POST", body });
      if (!response.ok) throw new Error(await errorMessage(response));
      const data = (await response.json()) as { fields: PlanFields };
      const next = { ...emptyFields, ...data.fields };
      setForm(next);
      const filled = fields.some((field) => next[field.key].trim());
      setPanel("fields");
      setStatus(filled ? "已从 Markdown 载入" : "模板已载入");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Markdown 载入失败");
    }
  }

  async function uploadReferences(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    const conflicts = duplicateReferenceNames(list, references);
    if (conflicts.length) {
      setStatus("");
      setError(`不能上传同名文件：${conflicts.map((name) => `「${name}」`).join("、")}`);
      return;
    }
    setUploading(true);
    setError("");
    const body = new FormData();
    for (const file of list) body.append("files", file);
    try {
      const response = await apiFetch("/api/references", { method: "POST", body });
      if (!response.ok) throw new Error(await errorMessage(response));
      const data = (await response.json()) as { files?: ReferenceFile[] };
      setReferences(data.files ?? []);
      setPanel("references");
      setStatus(`已上传 ${list.length} 个参考资料`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "参考资料上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function removeReference(name: string) {
    if (!window.confirm(`确定移除「${name}」？`)) return;
    setError("");
    try {
      const response = await apiFetch(`/api/references/${encodeURIComponent(name)}`, { method: "DELETE" });
      if (!response.ok) throw new Error(await errorMessage(response));
      const data = (await response.json()) as { files?: ReferenceFile[] };
      setReferences(data.files ?? []);
      setStatus(`已移除 ${name}`);
      if (noteTarget === name) {
        setNoteTarget(null);
        setNoteDraft("");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "移除失败");
    }
  }

  function openNote(file: ReferenceFile) {
    setNoteTarget(file.name);
    setNoteDraft(file.note ?? "");
    setError("");
    setStatus("");
  }

  function closeNote() {
    setNoteTarget(null);
    setNoteDraft("");
  }

  async function saveNote() {
    if (!noteTarget) return;
    setNoteSaving(true);
    setError("");
    try {
      const response = await apiFetch(`/api/references/${encodeURIComponent(noteTarget)}/note`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: noteDraft }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const data = (await response.json()) as { files?: ReferenceFile[] };
      setReferences(data.files ?? []);
      setStatus("注释已保存");
      closeNote();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "注释保存失败");
    } finally {
      setNoteSaving(false);
    }
  }

  const panelIndex = Math.max(
    0,
    panels.findIndex((item) => item.id === panel),
  );

  function stepPanel(delta: number) {
    const next = panels[panelIndex + delta];
    if (next) setPanel(next.id);
  }

  return (
    <div className="plan-board">
      <section className="settings-card plan-card">
        <div className="section-head plan-head">
          <div className="plan-intro">
            <h2>LCA 计划</h2>
          </div>
          <div className="plan-mode" role="radiogroup" aria-label="工作类型" data-mode={workMode}>
            <span className="plan-mode-thumb" aria-hidden="true" />
            <button
              type="button"
              role="radio"
              aria-checked={workMode === "new"}
              onClick={() => setWorkMode("new")}
            >
              新工作
            </button>
            <button type="button" role="radio" aria-checked={workMode === "revise"} onClick={() => setWorkMode("revise")}>
              修改工作
            </button>
          </div>
        </div>

        <div className="plan-pager">
          <button type="button" onClick={() => stepPanel(-1)} disabled={panelIndex === 0}>
            <ChevronLeft className="launch-icon" aria-hidden="true" />
            上一项
          </button>
          <div className="plan-tabs" role="tablist" aria-label="计划内容">
            {panels.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={panel === item.id}
                onClick={() => setPanel(item.id)}
              >
                <PanelIcon id={item.id} />
                {item.label}
                {item.id === "references" && references.length ? (
                  <em>{references.length}</em>
                ) : null}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => stepPanel(1)}
            disabled={panelIndex === panels.length - 1}
          >
            下一项
            <ChevronRight className="launch-icon" aria-hidden="true" />
          </button>
        </div>

        <div className="plan-panel" role="tabpanel">
          {panel === "fields" ? (
            <div className="plan-fields">
              <div className="plan-grid">
                {fields.map((field) => (
                  <label key={field.key} className="plan-field">
                    <span>{field.label}</span>
                    <small>{field.hint}</small>
                    <textarea
                      value={form[field.key]}
                      placeholder={field.placeholder}
                      onChange={(event) => update(field.key, event.target.value)}
                    />
                  </label>
                ))}
              </div>
              <div className="row plan-actions plan-import">
                <p>可以先下载模板写好，再上传。</p>
                <button type="button" onClick={() => void downloadTemplate()}>
                  <Download className="launch-icon" aria-hidden="true" />
                  下载模板
                </button>
                <button type="button" onClick={() => planInput.current?.click()}>
                  <Upload className="launch-icon" aria-hidden="true" />
                  上传 Markdown
                </button>
                <input
                  ref={planInput}
                  type="file"
                  accept=".md,.markdown,.txt,text/markdown,text/plain"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    if (file) void importPlan(file);
                  }}
                />
              </div>
            </div>
          ) : panel === "references" ? (
            <div className="plan-ref">
              <p className="settings-help">
                可以上传任意类型的文件，大小不限，不能有同名文件。Agent 只读取这些文件、项目知识库和 openLCA 数据库。
              </p>
              <div className="plan-ref-body">
                <div
                  className="plan-drop"
                  data-active={dragOver ? "true" : "false"}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDragOver(true);
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDragOver(false);
                    void uploadReferences(event.dataTransfer.files);
                  }}
                >
                  <FileText className="launch-icon" aria-hidden="true" />
                  <strong>{uploading ? "正在上传…" : "将参考资料拖到这里"}</strong>
                  <span>可以上传任意类型的文件，大小不限，不能有同名文件</span>
                  <button type="button" onClick={() => referenceInput.current?.click()} disabled={uploading}>
                    选择文件
                  </button>
                  <input
                    ref={referenceInput}
                    type="file"
                    multiple
                    hidden
                    onChange={(event) => {
                      const selected = event.target.files;
                      event.target.value = "";
                      if (selected) void uploadReferences(selected);
                    }}
                  />
                </div>
                <section className="plan-file-pane" aria-labelledby="uploaded-files-label">
                  <h3 id="uploaded-files-label" className="plan-file-pane-label">已上传文件</h3>
                  <div className="plan-file-scroll">
                  {references.length ? (
                    <ul className="plan-files">
                      {references.map((file, index) => (
                        <li
                          key={file.name}
                          data-active={noteTarget === file.name ? "true" : "false"}
                          data-noted={file.note?.trim() ? "true" : "false"}
                        >
                          <span className="plan-file-index">文件{index + 1}</span>
                          <strong className="plan-file-name" title={file.name}>
                            {file.name}
                          </strong>
                          <small>{formatSize(file.size)}</small>
                          <div className="plan-file-actions">
                            <button type="button" onClick={() => openNote(file)}>
                              <MessageSquare className="launch-icon" aria-hidden="true" />
                              注释
                            </button>
                            <button type="button" onClick={() => void removeReference(file.name)}>
                              <Trash2 className="launch-icon" aria-hidden="true" />
                              移除
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="settings-meta">还没有参考资料。</p>
                  )}
                  </div>
                </section>
              </div>
            </div>
          ) : panel === "workflow" ? (
            <WorkflowBoard mode={workMode} onModeChange={setWorkMode} />
          ) : (
            <PreviewBoard mode={workMode} fields={form} references={references} />
          )}
        </div>

        {status ? <p className="plan-status">{status}</p> : null}
        {error && !noteTarget ? <p className="status-banner error">{error}</p> : null}
      </section>
      <dialog
        ref={noteDialog}
        className="plan-note-dialog"
        aria-labelledby="plan-note-title"
        onClose={closeNote}
        onClick={(event) => {
          if (event.target === noteDialog.current) closeNote();
        }}
      >
        <form
          className="plan-note"
          onSubmit={(event) => {
            event.preventDefault();
            void saveNote();
          }}
        >
          <h2 id="plan-note-title">对「{noteTarget}」的注释</h2>
          <textarea
            id="plan-note"
            value={noteDraft}
            placeholder="注释会作为对agent的提示词，让你可以控制agent从这份文件中读取什么内容"
            onChange={(event) => setNoteDraft(event.target.value)}
          />
          {error ? <p className="status-banner error">{error}</p> : null}
          <div className="plan-note-actions">
            <button type="button" onClick={closeNote}>
              关闭
            </button>
            <button type="submit" className="primary" disabled={noteSaving}>
              {noteSaving ? "保存中…" : "保存"}
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
