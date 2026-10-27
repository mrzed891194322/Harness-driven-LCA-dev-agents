"use client";

import { useLocale } from "../../lib/i18n/locale-context";
import { translate } from "../../lib/i18n/messages";
import { uiLang } from "../../lib/run-status";
import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, ClipboardList, Download, FileText, MessageSquare, PenLine, Play, Trash2, Upload, Workflow } from "lucide-react";
import { PreviewBoard } from "../../components/plan/preview-board";
import { WorkflowBoard } from "../../components/plan/workflow-board";
import type { PlanFields } from "../../components/plan/plan-fields";
import { emptyPlanFields, normalizePlanFields } from "../../components/plan/plan-fields";
import { emptyStudyWork, StudyForm, type StudyWork } from "../../components/plan/study-form";
import { apiFetch } from "../../lib/api";
import {
  normalizeReferenceType,
  referenceRowKey,
  REFERENCE_TYPES,
  type ReferenceFile,
  type ReferenceType,
} from "../../lib/reference-types";
import { reviseWorkLocked } from "../../lib/revise-lock";

type PendingUpload = {
  file: File;
  name: string;
};

const emptyFields: PlanFields = emptyPlanFields();

type Panel = "fields" | "references" | "workflow" | "preview";

const panels: { id: Panel; labelKey: string }[] = [
  { id: "fields", labelKey: "plan.tab.fill" },
  { id: "references", labelKey: "plan.tab.refs" },
  { id: "workflow", labelKey: "plan.tab.workflow" },
  { id: "preview", labelKey: "plan.tab.preview" },
];

// Workflow id per work mode (the backend maps it to a fixed plan path).
function planWorkflow(mode: "new" | "revise"): string {
  return mode === "revise" ? "revise-lca" : "full-lca";
}

function PanelIcon({ id }: { id: Panel }) {
  const Icon = id === "fields" ? PenLine : id === "references" ? FileText : id === "workflow" ? Workflow : Play;
  return <Icon className="launch-icon" aria-hidden="true" />;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function duplicateReferenceNames(list: PendingUpload[], existing: ReferenceFile[]): string[] {
  const taken = new Set(existing.map((file) => file.name));
  const conflicts: string[] = [];
  for (const item of list) {
    if (taken.has(item.name)) conflicts.push(item.name);
    else taken.add(item.name);
  }
  return [...new Set(conflicts)];
}

function referenceName(file: File): string {
  const relative = file.webkitRelativePath.replaceAll("\\", "/").replace(/^\/+/, "");
  return relative || file.name;
}

function isSkippedReference(name: string): boolean {
  const parts = name.split("/").filter((part) => part && part !== ".");
  return parts.length === 0 || parts.some((part) => part.startsWith(".") || part === "__MACOSX");
}

function pendingFromFile(file: File, name = referenceName(file)): PendingUpload | null {
  const normalized = name.replaceAll("\\", "/").replace(/^\/+/, "");
  if (isSkippedReference(normalized)) return null;
  return { file, name: normalized };
}

function fileFromEntry(entry: FileSystemFileEntry): Promise<File> {
  return new Promise((resolve, reject) => {
    entry.file(resolve, reject);
  });
}

function readEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => {
    const all: FileSystemEntry[] = [];
    const read = () => {
      reader.readEntries((batch) => {
        if (!batch.length) {
          resolve(all);
          return;
        }
        all.push(...batch);
        read();
      }, reject);
    };
    read();
  });
}

async function pendingFromEntry(entry: FileSystemEntry): Promise<PendingUpload[]> {
  if (entry.name.startsWith(".") || entry.name === "__MACOSX") return [];
  if (entry.isFile) {
    const file = await fileFromEntry(entry as FileSystemFileEntry);
    const item = pendingFromFile(file, entry.fullPath.replace(/^\/+/, ""));
    return item ? [item] : [];
  }
  if (!entry.isDirectory) return [];
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  const children = await readEntries(reader);
  const nested = await Promise.all(children.map((child) => pendingFromEntry(child)));
  return nested.flat();
}

function downloadFilenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const quoted = /filename="([^"]+)"/i.exec(header);
  if (quoted?.[1]) return quoted[1];
  const bare = /filename=([^;]+)/i.exec(header);
  return bare?.[1]?.trim() || fallback;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string" && data.detail) return data.detail;
  } catch {
    // Response body is not JSON.
  }
  return translate(uiLang(), "plan.reqFail", { status: response.status });
}

export default function PlanPage() {
  const { t } = useLocale();
  const [form, setForm] = useState<PlanFields>(emptyFields);
  const [references, setReferences] = useState<ReferenceFile[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [workMode, setWorkMode] = useState<"new" | "revise">("new");
  const [pickedWorkflowId, setPickedWorkflowId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [panel, setPanel] = useState<Panel>("fields");
  const [formToken, setFormToken] = useState(0);
  const [planTemplateId, setPlanTemplateId] = useState("full-lifecycle");
  const [planTemplates, setPlanTemplates] = useState<
    { id: string; title: string; title_en?: string; description?: string }[]
  >([]);
  const [work, setWork] = useState<StudyWork>(() => emptyStudyWork());
  const [noteTarget, setNoteTarget] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [planContent, setPlanContent] = useState("");
  const [planPath, setPlanPath] = useState("");
  const savedPlan = useRef("");
  // Only save after the user actually changed something (edit). Loading, hydrating
  // the form and importing must never rewrite the plan file (a stale tab rewrote it).
  const dirty = useRef(false);
  const saveChain = useRef<Promise<void>>(Promise.resolve());
  useEffect(() => {
    setPickedWorkflowId(null);
  }, [workMode]);

  const workflowName = planWorkflow(workMode);
  const planInput = useRef<HTMLInputElement>(null);
  const referenceInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const noteDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const name = planWorkflow(workMode);
    apiFetch(`/api/plan?workflow=${encodeURIComponent(name)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(await errorMessage(response));
        return response.json() as Promise<{
          fields?: PlanFields;
          references?: ReferenceFile[];
          content?: string;
          path?: string;
        }>;
      })
      .then((data) => {
        dirty.current = false;
        const next = normalizePlanFields(data.fields, planTemplateId);
        setForm(next);
        if (next.template_id) setPlanTemplateId(next.template_id);
        setFormToken((token) => token + 1);
        setReferences(data.references ?? []);
        setPlanContent(data.content ?? "");
        setPlanPath(data.path ?? "");
        setLoaded(true);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : t("plan.readFail"));
      });
  }, [workMode]);

  // Autosave: persist field edits (incl. LCIA method) without executing. The
  // backend writes the plan file named by the workflow YAML `plan:`.
  useEffect(() => {
    if (!loaded || !workflowName) return;
    const body = JSON.stringify(work.plan);
    if (!dirty.current) {
      savedPlan.current = body;
      return;
    }
    if (body === savedPlan.current) return;
    const target = workflowName;
    const timer = window.setTimeout(() => {
      // Serialize PUTs so an older save can never land after a newer one.
      saveChain.current = saveChain.current.then(async () => {
        try {
          const response = await apiFetch(`/api/plan?workflow=${encodeURIComponent(target)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body,
            keepalive: true,
          });
          if (!response.ok) throw new Error(await errorMessage(response));
          const data = (await response.json()) as { content?: string; path?: string };
          savedPlan.current = body;
          if (typeof data.content === "string") setPlanContent(data.content);
          if (data.path) setPlanPath(data.path);
          setStatus(t("plan.autoSaved"));
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : t("plan.autoSaveFail"));
        }
      });
    }, 400);
    return () => window.clearTimeout(timer);
  }, [loaded, work.plan, workflowName]);

  useEffect(() => {
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  useEffect(() => {
    if (reviseWorkLocked) return;
    if (new URLSearchParams(window.location.search).get("mode") === "revise") {
      setWorkMode("revise");
    }
  }, []);

  useEffect(() => {
    const dialog = noteDialog.current;
    if (!dialog) return;
    if (noteTarget && !dialog.open) dialog.showModal();
    if (!noteTarget && dialog.open) dialog.close();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, [noteTarget]);

  useEffect(() => {
    let cancelled = false;
    apiFetch("/api/plan/templates")
      .then(async (response) => {
        const data = (await response.json()) as {
          templates?: { id: string; title: string; title_en?: string; description?: string }[];
        };
        if (!response.ok || cancelled) return;
        const list = data.templates || [];
        setPlanTemplates(list);
        if (list.length && !list.some((item) => item.id === planTemplateId)) {
          setPlanTemplateId(list[0].id);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function downloadTemplate() {
    setError("");
    try {
      const response = await apiFetch(
        `/api/plan/template?template_id=${encodeURIComponent(planTemplateId)}`,
      );
      if (!response.ok) throw new Error(await errorMessage(response));
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = downloadFilenameFromDisposition(
        response.headers.get("Content-Disposition"),
        `lca-plan-${planTemplateId}.yaml`,
      );
      link.click();
      URL.revokeObjectURL(url);
      // Success: no bottom-bar status line (errors still use setError).
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("plan.templateFail"));
    }
  }

  async function importPlan(file: File) {
    setError("");
    const suffix = file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")).toLowerCase() : "";
    if (suffix !== ".yaml" && suffix !== ".yml") {
      setError(t("plan.yamlNeedExt"));
      return;
    }
    const overwrite = planContent.trim().length > 0;
    if (
      overwrite &&
      !window.confirm(t("plan.confirmOverwrite", { path: planPath ? t("plan.pathParen", { path: planPath }) : "" }))
    ) {
      return;
    }
    const body = new FormData();
    body.append("file", file);
    const query = new URLSearchParams({
      workflow: planWorkflow(workMode),
    });
    if (overwrite) query.set("overwrite", "true");
    try {
      const response = await apiFetch(`/api/plan/import?${query.toString()}`, {
        method: "POST",
        body,
      });
      if (!response.ok) {
        // Illegal YAML / illegal item: show error and keep current form (no half-render).
        throw new Error(await errorMessage(response));
      }
      const data = (await response.json()) as {
        fields: PlanFields;
        path?: string;
        content?: string;
        template_id?: string;
      };
      const next = normalizePlanFields(data.fields, data.template_id || planTemplateId);
      if (!Array.isArray(data.fields?.items) || !data.fields.items.length) {
        throw new Error(t("plan.yamlFail"));
      }
      // The backend already wrote the imported file; don't autosave over it.
      dirty.current = false;
      setForm(next);
      setFormToken((token) => token + 1);
      setPlanPath(data.path ?? planPath);
      if (next.template_id) setPlanTemplateId(next.template_id);
      setPlanContent(typeof data.content === "string" ? data.content : await file.text());
      setPanel("fields");
      setStatus("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("plan.yamlFail"));
    }
  }

  function queueReferences(files: FileList | File[]) {
    const raw = Array.from(files);
    if (!raw.length) return;
    const list = raw
      .map((file) => pendingFromFile(file))
      .filter((item): item is PendingUpload => item !== null);
    void uploadReferences(list);
  }

  async function uploadDropped(entries: FileSystemEntry[]) {
    setUploading(true);
    setError("");
    try {
      const nested = await Promise.all(entries.map((entry) => pendingFromEntry(entry)));
      await uploadReferences(nested.flat(), { alreadyUploading: true });
    } catch (reason) {
      setUploading(false);
      setError(reason instanceof Error ? reason.message : t("plan.refUploadFail"));
    }
  }

  async function uploadReferences(list: PendingUpload[], options?: { alreadyUploading?: boolean }) {
    if (!list.length) {
      setUploading(false);
      setStatus("");
      setError(t("plan.noUpload"));
      return;
    }
    const conflicts = duplicateReferenceNames(list, references);
    if (conflicts.length) {
      setUploading(false);
      setStatus("");
      setError(t("plan.dupUpload", { names: conflicts.map((name) => t("plan.quoteName", { name })).join(t("plan.joinSep")) }));
      return;
    }
    if (!options?.alreadyUploading) setUploading(true);
    setError("");
    const body = new FormData();
    for (const item of list) {
      body.append("files", item.file, item.file.name);
      body.append("paths", item.name);
    }
    try {
      const response = await apiFetch("/api/references", { method: "POST", body });
      if (!response.ok) throw new Error(await errorMessage(response));
      const data = (await response.json()) as { files?: ReferenceFile[] };
      setReferences(data.files ?? []);
      setPanel("references");
      setStatus(t("plan.uploadedN", { n: list.length }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("plan.refUploadFail"));
    } finally {
      setUploading(false);
    }
  }

  async function updateReferenceType(file: ReferenceFile, nextType: ReferenceType) {
    const current = normalizeReferenceType(file.type);
    if (current === nextType) return;
    setError("");
    try {
      const query = `?ref_type=${encodeURIComponent(current)}`;
      const response = await apiFetch(`/api/references/${encodeURIComponent(file.name)}/type${query}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: nextType }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const data = (await response.json()) as { files?: ReferenceFile[] };
      setReferences(data.files ?? []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("plan.refTypeFail"));
    }
  }

  async function removeReference(file: ReferenceFile) {
    const name = file.name;
    if (!window.confirm(t("plan.confirmRemove", { name }))) return;
    setError("");
    try {
      const query = `?ref_type=${encodeURIComponent(normalizeReferenceType(file.type))}`;
      const response = await apiFetch(`/api/references/${encodeURIComponent(name)}${query}`, { method: "DELETE" });
      if (!response.ok) throw new Error(await errorMessage(response));
      const data = (await response.json()) as { files?: ReferenceFile[] };
      setReferences(data.files ?? []);
      setStatus(t("plan.removed", { name }));
      if (noteTarget === name) {
        setNoteTarget(null);
        setNoteDraft("");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("plan.removeFail"));
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
      const target = references.find((file) => file.name === noteTarget);
      const query = target ? `?ref_type=${encodeURIComponent(normalizeReferenceType(target.type))}` : "";
      const response = await apiFetch(`/api/references/${encodeURIComponent(noteTarget)}/note${query}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: noteDraft }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const data = (await response.json()) as { files?: ReferenceFile[] };
      setReferences(data.files ?? []);
      setStatus(t("plan.noteSaved"));
      closeNote();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("plan.noteSaveFail"));
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
            <h2>
              <ClipboardList className="plan-title-icon" size={20} strokeWidth={1.75} aria-hidden="true" />
              {t("plan.title")}
            </h2>
          </div>
          <div className="plan-mode" role="radiogroup" aria-label={t("plan.workType")} data-mode={workMode}>
            <span className="plan-mode-thumb" aria-hidden="true" />
            <button
              type="button"
              role="radio"
              aria-checked={workMode === "new"}
              onClick={() => setWorkMode("new")}
            >
              {t("plan.modeNew")}
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={workMode === "revise"}
              disabled={reviseWorkLocked}
              title={reviseWorkLocked ? t("common.locked") : undefined}
              onClick={() => {
                if (!reviseWorkLocked) setWorkMode("revise");
              }}
            >
              {t("plan.modeRevise")}
            </button>
          </div>
        </div>

        <div className="plan-pager">
          <button type="button" onClick={() => stepPanel(-1)} disabled={panelIndex === 0}>
            <ChevronLeft className="launch-icon" aria-hidden="true" />
            {t("plan.prev")}
          </button>
          <div className="plan-tabs" role="tablist" aria-label={t("plan.content")}>
            {panels.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={panel === item.id}
                onClick={() => setPanel(item.id)}
              >
                <PanelIcon id={item.id} />
                {t(item.labelKey)}
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
            {t("plan.next")}
            <ChevronRight className="launch-icon" aria-hidden="true" />
          </button>
        </div>

        <div className="plan-panel" role="tabpanel">
          <div
            className="plan-fields"
            hidden={panel !== "fields"}
            onChangeCapture={() => {
              dirty.current = true;
            }}
            onClickCapture={(event) => {
              if ((event.target as HTMLElement).closest(".plan-study button")) dirty.current = true;
            }}
          >
            <StudyForm
              source={form}
              sourceKey={formToken}
              onWork={setWork}
              templateId={planTemplateId}
            />
            <div className="row plan-actions plan-import">
              <div className="plan-template-pick">
                <label htmlFor="plan-template-select">{t("plan.templatePick")}</label>
                <select
                  id="plan-template-select"
                  value={planTemplateId}
                  title={t("plan.templatePickHelp")}
                  onChange={(event) => {
                    const nextId = event.target.value;
                    setPlanTemplateId(nextId);
                    dirty.current = true;
                    setForm((prev) => ({ ...prev, template_id: nextId }));
                    setFormToken((token) => token + 1);
                  }}
                >
                  {(planTemplates.length
                    ? planTemplates
                    : [
                        { id: "full-lifecycle", title: t("plan.template.full-lifecycle") },
                        { id: "bom-only", title: t("plan.template.bom-only") },
                        { id: "lca-only", title: t("plan.template.lca-only") },
                      ]
                  ).map((item) => {
                    const titleKey = `plan.template.${item.id}` as const;
                    const localized = t(titleKey);
                    return (
                      <option key={item.id} value={item.id}>
                        {localized !== titleKey ? localized : item.title}
                      </option>
                    );
                  })}
                </select>
              </div>
              {status ? <p className="plan-status">{status}</p> : null}
              <div className="plan-import-actions">
                <p className="plan-import-hint">{t("plan.importHint")}</p>
                <button type="button" onClick={() => void downloadTemplate()}>
                  <Download className="launch-icon" aria-hidden="true" />
                  {t("plan.downloadTemplate")}
                </button>
                <button type="button" onClick={() => planInput.current?.click()}>
                  <Upload className="launch-icon" aria-hidden="true" />
                  {t("plan.uploadPlan")}
                </button>
                <input
                  ref={planInput}
                  type="file"
                  accept=".yaml,.yml,application/yaml,text/yaml"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void importPlan(file);
                  }}
                />
              </div>
            </div>
          </div>
          {panel === "references" ? (
            <div className="plan-ref">
              <p className="settings-help">
                {t("plan.noteHint")}
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
                    const entries: FileSystemEntry[] = [];
                    for (const item of event.dataTransfer.items) {
                      if (item.kind !== "file") continue;
                      const entry = item.webkitGetAsEntry?.();
                      if (entry) entries.push(entry);
                    }
                    if (entries.length) {
                      void uploadDropped(entries);
                      return;
                    }
                    queueReferences(event.dataTransfer.files);
                  }}
                >
                  <FileText className="launch-icon" aria-hidden="true" />
                  <strong>{uploading ? t("plan.uploading") : t("plan.dropRefs")}</strong>
                  <span>{t("plan.uploadHelp")}</span>
                  <div className="plan-drop-actions">
                    <button type="button" onClick={() => referenceInput.current?.click()} disabled={uploading}>
                      {t("plan.pickFiles")}
                    </button>
                    <button type="button" onClick={() => folderInput.current?.click()} disabled={uploading}>
                      {t("plan.pickFolder")}
                    </button>
                  </div>
                  <input
                    ref={referenceInput}
                    type="file"
                    multiple
                    hidden
                    onChange={(event) => {
                      if (event.target.files?.length) queueReferences(event.target.files);
                    }}
                  />
                  <input
                    ref={folderInput}
                    type="file"
                    multiple
                    hidden
                    // Native directory picker (Chromium, Firefox, Safari).
                    {...{ webkitdirectory: "", directory: "" }}
                    onChange={(event) => {
                      if (event.target.files?.length) queueReferences(event.target.files);
                    }}
                  />
                </div>
                <section className="plan-file-pane" aria-labelledby="uploaded-files-label">
                  <h3 id="uploaded-files-label" className="plan-file-pane-label">{t("plan.uploadedFiles")}</h3>
                  <div className="plan-file-scroll">
                  {references.length ? (
                    <ul className="plan-files">
                      {references.map((file) => (
                        <li
                          key={referenceRowKey(file)}
                          data-active={noteTarget === file.name ? "true" : "false"}
                          data-noted={file.note?.trim() ? "true" : "false"}
                        >
                          <div className="plan-file-actions">
                            <button type="button" onClick={() => openNote(file)}>
                              <MessageSquare className="launch-icon" aria-hidden="true" />
                              {t("plan.note")}
                            </button>
                            <button type="button" onClick={() => void removeReference(file)}>
                              <Trash2 className="launch-icon" aria-hidden="true" />
                              {t("plan.remove")}
                            </button>
                          </div>
                          <strong className="plan-file-name" title={file.name}>
                            {file.name}
                          </strong>
                          <small>{formatSize(file.size)}</small>
                          <div
                            className="plan-file-type-row"
                            onMouseDown={(event) => event.stopPropagation()}
                            onClick={(event) => event.stopPropagation()}
                          >
                            <span className="plan-file-type-prefix">{t("plan.refTypePrefix")}</span>
                            <select
                              className="plan-file-type"
                              value={normalizeReferenceType(file.type)}
                              aria-label={t("plan.refTypeLabel", { name: file.name })}
                              onChange={(event) =>
                                void updateReferenceType(file, event.target.value as ReferenceType)
                              }
                            >
                              {REFERENCE_TYPES.map((kind) => (
                                <option key={kind} value={kind}>
                                  {t(`plan.refType.${kind}`)}
                                </option>
                              ))}
                            </select>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="settings-meta">{t("plan.noRefs")}</p>
                  )}
                  </div>
                </section>
              </div>
            </div>
          ) : panel === "workflow" ? (
            <WorkflowBoard mode={workMode} pickedId={pickedWorkflowId} onPickWorkflow={setPickedWorkflowId} />
          ) : panel === "preview" ? (
            <PreviewBoard mode={workMode} work={work} references={references} workflowId={pickedWorkflowId} />
          ) : null}
        </div>

        {panel !== "fields" && status ? <p className="plan-status">{status}</p> : null}
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
          <h2 id="plan-note-title">{t("plan.noteTitle", { name: noteTarget ?? "" })}</h2>
          <textarea
            id="plan-note"
            value={noteDraft}
            placeholder={t("plan.noteHelp")}
            onChange={(event) => setNoteDraft(event.target.value)}
          />
          {error ? <p className="status-banner error">{error}</p> : null}
          <div className="plan-note-actions">
            <button type="button" onClick={closeNote}>
              {t("common.close")}
            </button>
            <button type="submit" className="primary" disabled={noteSaving}>
              {noteSaving ? t("common.saving") : t("common.save")}
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
