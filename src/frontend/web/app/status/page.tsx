"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Bot, Cpu, List, RefreshCw, Save, Settings, Wrench } from "lucide-react";
import Link from "next/link";
import { useSettings } from "../../components/settings/settings-context";
import { apiFetch } from "../../lib/api";
import { useLocale } from "../../lib/i18n/locale-context";

type Check = { ok: boolean; message: string };

type LcaTool = {
  id: string;
  name: string;
  ok: boolean;
  status?: "ok" | "busy" | "down";
  message: string;
  host?: string;
  port?: number;
};

function toolBadgeLabel(tool: LcaTool, t: (k: string) => string): string {
  if (tool.ok) return t("status.toolAvailable");
  return tool.status === "busy" ? t("status.toolBusy") : t("status.toolDown");
}

type AvailableProvider = {
  id: string;
  name: string;
  auth?: string;
};

type LoadedModel = {
  id: string;
  name: string;
};

type ModelListState = {
  state: "loading" | "ok" | "fail";
  models: LoadedModel[];
  message: string;
};

type Diagnostics = {
  node: Check;
  pi_agents: Check & { version?: string };
  toolchain?: Partial<Record<"typescript" | "next" | "npm" | "pi_sdk" | "python" | "uv", string>>;
  python_agent: Check;
  openlca: Check & { host?: string; port?: number; status?: LcaTool["status"] };
  lca_tools?: LcaTool[];
  available_providers?: AvailableProvider[];
};

function isDiagnostics(value: unknown): value is Diagnostics {
  if (!value || typeof value !== "object") return false;
  const row = value as Diagnostics;
  return Boolean(row.pi_agents && row.python_agent && row.openlca && "ok" in row.pi_agents);
}

function statusProviderName(provider: AvailableProvider): string {
  if (provider.id === "openai") return "OpenAI";
  return provider.name;
}

function OpenLcaToolPanel({ tool, onSaved }: { tool: LcaTool; onSaved: () => Promise<void> }) {
  const { t } = useLocale();
  const [portDraft, setPortDraft] = useState(tool.port != null ? String(tool.port) : "");
  const [portBusy, setPortBusy] = useState(false);
  const [portError, setPortError] = useState("");

  useEffect(() => {
    if (tool.port != null) setPortDraft(String(tool.port));
  }, [tool.port]);

  async function savePort() {
    const port = Number(portDraft);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      setPortError(t("status.portInvalid"));
      return;
    }
    setPortBusy(true);
    setPortError("");
    try {
      const response = await apiFetch("/api/lca/openlca", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ port }),
      });
      const data = (await response.json().catch(() => ({}))) as { detail?: string };
      if (!response.ok) throw new Error(data.detail || t("status.portSaveFail"));
      await onSaved();
    } catch (error: unknown) {
      setPortError(error instanceof Error ? error.message : t("status.portSaveFail"));
    } finally {
      setPortBusy(false);
    }
  }

  return (
    <div className="tool-panel">
      <div className="tool-port-row">
        <label htmlFor="openlca-port">{t("status.ipcPort")}</label>
        <input
          id="openlca-port"
          type="number"
          min={1}
          max={65535}
          inputMode="numeric"
          value={portDraft}
          onChange={(event) => setPortDraft(event.target.value)}
        />
        <button type="button" onClick={() => void savePort()} disabled={portBusy}>
          <Save size={16} strokeWidth={1.75} aria-hidden="true" />
          {portBusy ? t("common.saving") : t("common.save")}
        </button>
      </div>
      {portError ? <p className="settings-help">{portError}</p> : null}
      <div className="tool-status-row">
        <span>{t("status.currentState")}</span>
        <span className={`badge ${tool.ok ? "badge-ok" : "badge-warn"}`}>
          {toolBadgeLabel(tool, t)}
        </span>
      </div>
    </div>
  );
}

function ToolConnectionPanel({ tool, onOpenLcaSaved }: { tool: LcaTool; onOpenLcaSaved: () => Promise<void> }) {
  const { t } = useLocale();
  if (tool.id === "openlca") return <OpenLcaToolPanel tool={tool} onSaved={onOpenLcaSaved} />;
  return (
    <div className="tool-panel">
      <div className="tool-status-row">
        <span>{t("status.currentState")}</span>
        <span className={`badge ${tool.ok ? "badge-ok" : "badge-warn"}`}>
          {toolBadgeLabel(tool, t)}
        </span>
      </div>
    </div>
  );
}

function toolsFromDiag(diag: Diagnostics): LcaTool[] {
  if (diag.lca_tools?.length) return diag.lca_tools;
  return [
    {
      id: "openlca",
      name: "openLCA",
      ok: diag.openlca.ok,
      status: diag.openlca.status,
      message: diag.openlca.message,
      host: diag.openlca.host,
      port: diag.openlca.port,
    },
  ];
}

export default function StatusPage() {
  const { t } = useLocale();
  const { openSettings, revision } = useSettings();
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [providers, setProviders] = useState<AvailableProvider[] | null>(null);
  const [providerError, setProviderError] = useState("");
  const [modelBusy, setModelBusy] = useState(false);
  const [selectedTool, setSelectedTool] = useState("openlca");
  const [openProvider, setOpenProvider] = useState<string | null>(null);
  const [modelLists, setModelLists] = useState<Record<string, ModelListState>>({});

  const refresh = useCallback(async () => {
    setBusy(true);
    setLoadError("");
    try {
      const envRes = await apiFetch("/api/diagnostics/environment");
      const env = (await envRes.json()) as unknown;
      if (!envRes.ok || !isDiagnostics(env)) {
        throw new Error(t("status.diagUnavailable", { status: envRes.status }));
      }
      setDiag(env);
    } catch (error: unknown) {
      setDiag(null);
      setLoadError(error instanceof Error ? error.message : t("status.diagLoadFail"));
    } finally {
      setBusy(false);
    }
  }, [t]);

  const refreshProviders = useCallback(async () => {
    setModelBusy(true);
    setProviderError("");
    try {
      const response = await apiFetch("/api/models/providers");
      const data = (await response.json()) as { providers?: AvailableProvider[]; detail?: string };
      if (!response.ok || !Array.isArray(data.providers)) {
        throw new Error(data.detail || t("status.providerFail"));
      }
      setProviders(data.providers);
    } catch (error: unknown) {
      setProviderError(error instanceof Error ? error.message : t("status.providerFail"));
    } finally {
      setModelBusy(false);
    }
  }, [t]);

  useEffect(() => {
    if (revision > 0) {
      setOpenProvider(null);
      setModelLists({});
    }
    void refresh();
    void refreshProviders();
  }, [refresh, refreshProviders, revision]);

  useEffect(() => {
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  const tools = diag ? toolsFromDiag(diag) : [];
  const providerRows = providers ?? [];
  const activeTool = tools.find((tool) => tool.id === selectedTool) ?? tools[0];

  async function toggleProvider(providerId: string) {
    if (openProvider === providerId) {
      setOpenProvider(null);
      return;
    }
    setOpenProvider(providerId);
    if (modelLists[providerId]?.state === "ok") return;
    setModelLists((prev) => ({
      ...prev,
      [providerId]: { state: "loading", models: [], message: "" },
    }));
    try {
      const response = await apiFetch(
        `/api/models/providers/${encodeURIComponent(providerId)}/models`,
      );
      const data = (await response.json()) as {
        ok?: boolean;
        models?: LoadedModel[];
        message?: string;
        detail?: string;
      };
      if (!response.ok || data.ok === false) {
        setModelLists((prev) => ({
          ...prev,
          [providerId]: {
            state: "fail",
            models: [],
            message: data.message || data.detail || t("status.modelLoadFail"),
          },
        }));
        return;
      }
      setModelLists((prev) => ({
        ...prev,
        [providerId]: { state: "ok", models: data.models ?? [], message: data.message || "" },
      }));
    } catch (error: unknown) {
      setModelLists((prev) => ({
        ...prev,
        [providerId]: {
          state: "fail",
          models: [],
          message: error instanceof Error ? error.message : t("status.modelLoadFail"),
        },
      }));
    }
  }

  const typescriptReady = Boolean(diag?.node.ok);
  const pythonReady = Boolean(diag?.python_agent.ok);
  const environments = [
    {
      id: "typescript",
      title: "TypeScript",
      ready: typescriptReady,
      message: diag?.node.message || "",
      tools: [
        { name: "TypeScript", version: diag?.toolchain?.typescript || "", note: t("status.noteTs"), src: "/toolchain/typescript.svg" },
        { name: "npm", version: diag?.toolchain?.npm || "", note: t("status.noteNpm"), src: "/toolchain/npm.svg" },
        { name: "Pi SDK", version: diag?.toolchain?.pi_sdk || diag?.pi_agents.version || "", note: t("status.notePi"), src: "/toolchain/pi.svg" },
        { name: "Next.js", version: diag?.toolchain?.next || "", note: t("status.noteNext"), src: "/toolchain/next.svg" },
      ],
    },
    {
      id: "python",
      title: "Python",
      ready: pythonReady,
      message: diag?.python_agent.message || "",
      tools: [
        { name: "Python", version: diag?.toolchain?.python || "", note: t("status.notePython"), src: "/toolchain/python.svg" },
        { name: "uv", version: diag?.toolchain?.uv || "", note: t("status.noteUv"), src: "/toolchain/uv.svg" },
      ],
    },
  ];

  return (
    <div className="status-board">
      <section className="settings-card status-runtime-card">
        <h3>
          <Cpu size={18} strokeWidth={1.75} aria-hidden="true" />
          {t("status.envTitle")}
        </h3>
        {diag ? (
          <div className="status-env-list">
            {environments.map((env) => (
              <section key={env.id} className="status-env">
                <header className="status-env-head">
                  <strong>{env.title}</strong>
                  <span className={`badge ${env.ready ? "badge-ok" : "badge-warn"}`}>
                    {env.ready ? t("status.ready") : t("status.notReady")}
                  </span>
                </header>
                {env.ready ? (
                  <ul className="status-toolchain">
                    {env.tools.filter((tool) => tool.version).map((tool) => (
                      <li key={tool.name}>
                        <img src={tool.src} alt="" />
                        <strong>{tool.name}</strong>
                        <span className="status-tool-version">{tool.version}</span>
                        <span className="status-tool-note">{tool.note}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="settings-help">{env.message || t("status.envNotReady")}</p>
                )}
              </section>
            ))}
          </div>
        ) : (
          <p className="settings-help">{loadError || t("status.checkingRuntime")}</p>
        )}
        <div className="status-runtime-actions">
          <button type="button" onClick={() => void refresh()} disabled={busy}>
            <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
            {busy ? t("status.checking") : t("status.recheck")}
          </button>
          <button type="button" onClick={() => openSettings("general")}>
            <Settings size={16} strokeWidth={1.75} aria-hidden="true" />
            {t("status.configProject")}
          </button>
        </div>
      </section>

      <section className="settings-card status-model-card">
        <h3>
          <Bot size={18} strokeWidth={1.75} aria-hidden="true" />
          {t("status.modelsTitle")}
        </h3>
        {providers === null ? (
          <p className="settings-help">{providerError || t("status.checkingProviders")}</p>
        ) : providerRows.length === 0 ? (
          <p className="settings-help">
            {providerError || t("status.noProviders")}
          </p>
        ) : (
          <>
            <h4 className="status-provider-label">{t("status.configuredProviders")}</h4>
            <ul className="status-model-body diag-list">
            {providerRows.map((provider) => {
              const open = openProvider === provider.id;
              const detail = modelLists[provider.id];
              return (
                <li key={provider.id} className="status-provider">
                  <div className="status-provider-head">
                    <span className="status-provider-dot" role="img" aria-label={t("common.connected")} />
                    <span>{statusProviderName(provider)}</span>
                    <button
                      type="button"
                      aria-expanded={open}
                      onClick={() => void toggleProvider(provider.id)}
                    >
                      <List size={14} strokeWidth={1.75} aria-hidden="true" />
                      {open ? t("common.collapse") : t("status.modelList")}
                    </button>
                  </div>
                  {open ? (
                    <div className="status-provider-detail">
                      {detail?.state === "loading" || !detail ? (
                        <p className="settings-help">{t("status.loadingModels")}</p>
                      ) : detail.state === "fail" ? (
                        <p className="settings-help">{detail.message}</p>
                      ) : detail.models.length === 0 ? (
                        <p className="settings-help">
                          {detail.message || t("status.noModels")}
                        </p>
                      ) : (
                        <ul className="model-detail-list">
                          {detail.models.map((model) => (
                            <li key={model.id}>{model.name}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ) : null}
                </li>
              );
            })}
            </ul>
          </>
        )}
        <div className="status-model-actions">
          <button
            type="button"
            onClick={() => {
              setOpenProvider(null);
              setModelLists({});
              void refreshProviders();
            }}
            disabled={modelBusy}
          >
            <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
            {modelBusy ? t("common.refreshing") : t("status.refreshState")}
          </button>
          <button type="button" onClick={() => openSettings("models")}>
            <Settings size={16} strokeWidth={1.75} aria-hidden="true" />
            {t("status.configModels")}
          </button>
        </div>
      </section>

      <section className="settings-card status-tool-card">
        <h3>
          <Wrench size={18} strokeWidth={1.75} aria-hidden="true" />
          {t("status.lcaTools")}
        </h3>
        <div className="status-tool-body">
          <h4 className="status-provider-label">{t("status.currentTool")}</h4>
          {tools.length ? (
            <>
              <div className="tool-switch-row">
                <div className="tool-switch" role="tablist" aria-label={t("status.lcaTools")}>
                  {tools.map((tool) => (
                    <button
                      key={tool.id}
                      type="button"
                      role="tab"
                      aria-selected={tool.id === activeTool?.id}
                      onClick={() => setSelectedTool(tool.id)}
                    >
                      {tool.id === "openlca" ? (
                        <>
                          <img src="/toolchain/openlca.svg" alt="" />
                          <strong>openLCA</strong>
                          <span>{t("status.openlcaDesc")}</span>
                        </>
                      ) : (
                        tool.name
                      )}
                    </button>
                  ))}
                </div>
                <p className="tool-switch-pending">{t("status.otherToolsPending")}</p>
              </div>
              {activeTool ? (
                <ToolConnectionPanel key={activeTool.id} tool={activeTool} onOpenLcaSaved={refresh} />
              ) : null}
            </>
          ) : (
            <p className="settings-help">{loadError ? t("status.diagNotLoaded") : t("status.checkingLca")}</p>
          )}
        </div>
        <div className="status-tool-actions">
          <button type="button" onClick={() => void refresh()} disabled={busy}>
            <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
            {busy ? t("common.refreshing") : t("status.refreshState")}
          </button>
          <Link href="/plan" className="status-start">
            {t("status.startLca")}
            <ArrowRight size={16} strokeWidth={1.75} aria-hidden="true" />
          </Link>
        </div>
      </section>
    </div>
  );
}
