"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, RefreshCw, Settings } from "lucide-react";
import Link from "next/link";
import { useSettings } from "../../components/settings/settings-context";

type Check = { ok: boolean; message: string };

type LcaTool = {
  id: string;
  name: string;
  ok: boolean;
  message: string;
  host?: string;
  port?: number;
};

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
  pi_agents: Check;
  python_agent: Check;
  openlca: Check & { host?: string; port?: number };
  lca_tools?: LcaTool[];
  available_providers?: AvailableProvider[];
};

function isDiagnostics(value: unknown): value is Diagnostics {
  if (!value || typeof value !== "object") return false;
  const row = value as Diagnostics;
  return Boolean(row.pi_agents && row.python_agent && row.openlca && "ok" in row.pi_agents);
}

function toolsFromDiag(diag: Diagnostics): LcaTool[] {
  if (diag.lca_tools?.length) return diag.lca_tools;
  return [
    {
      id: "openlca",
      name: "openLCA",
      ok: diag.openlca.ok,
      message: diag.openlca.message,
      host: diag.openlca.host,
      port: diag.openlca.port,
    },
  ];
}

export default function StatusPage() {
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
      const envRes = await fetch("/api/diagnostics/environment");
      const env = (await envRes.json()) as unknown;
      if (!envRes.ok || !isDiagnostics(env)) {
        throw new Error(
          `环境诊断不可用（HTTP ${envRes.status}）。请确认后端已按 .env 的 GUI_API_PORT 启动。`,
        );
      }
      setDiag(env);
    } catch (error: unknown) {
      setDiag(null);
      setLoadError(error instanceof Error ? error.message : "加载诊断失败");
    } finally {
      setBusy(false);
    }
  }, []);

  const refreshProviders = useCallback(async () => {
    setModelBusy(true);
    setProviderError("");
    try {
      const response = await fetch("/api/models/providers");
      const data = (await response.json()) as { providers?: AvailableProvider[]; detail?: string };
      if (!response.ok || !Array.isArray(data.providers)) {
        throw new Error(data.detail || "无法读取供应商状态");
      }
      setProviders(data.providers);
    } catch (error: unknown) {
      setProviderError(error instanceof Error ? error.message : "无法读取供应商状态");
    } finally {
      setModelBusy(false);
    }
  }, []);

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
      const response = await fetch(
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
            message: data.message || data.detail || "无法加载模型",
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
          message: error instanceof Error ? error.message : "无法加载模型",
        },
      }));
    }
  }

  const pi = diag?.pi_agents;
  const python = diag?.python_agent;
  const piText = pi?.ok ? diag?.node?.message || pi.message : pi?.message;

  return (
    <div className="status-board">
      <section className="settings-card">
        <div className="section-head">
          <h3>运行时</h3>
          <button type="button" onClick={() => void refresh()} disabled={busy}>
            {busy ? "检查中…" : "重新检查"}
          </button>
        </div>
        {diag && pi && python ? (
          <ul className="diag-list">
            <li>
              <span className={`badge ${pi.ok ? "badge-ok" : "badge-warn"}`}>
                {pi.ok ? "就绪" : "未就绪"}
              </span>
              <span>Pi：{piText}</span>
            </li>
            <li>
              <span className={`badge ${python.ok ? "badge-ok" : "badge-warn"}`}>
                {python.ok ? "就绪" : "未就绪"}
              </span>
              <span>Python：{python.message}</span>
            </li>
          </ul>
        ) : (
          <p className="settings-help">{loadError || "正在检查运行时…"}</p>
        )}
      </section>

      <section className="settings-card status-model-card">
        <h3>模型可用性</h3>
        {providers === null ? (
          <p className="settings-help">{providerError || "正在检查供应商…"}</p>
        ) : providerRows.length === 0 ? (
          <p className="settings-help">
            {providerError || "还没有可用供应商。请在设置中配置模型。"}
          </p>
        ) : (
          <ul className="status-model-body diag-list">
            {providerRows.map((provider) => {
              const open = openProvider === provider.id;
              const detail = modelLists[provider.id];
              return (
                <li key={provider.id} className="status-provider">
                  <div className="status-provider-head">
                    <span className="badge badge-ok">可用</span>
                    <span>
                      {provider.name}
                      <span className="settings-meta"> · {provider.id}</span>
                    </span>
                    <button
                      type="button"
                      aria-expanded={open}
                      onClick={() => void toggleProvider(provider.id)}
                    >
                      {open ? "收起" : "详情"}
                    </button>
                  </div>
                  {open ? (
                    <div className="status-provider-detail">
                      {detail?.state === "loading" || !detail ? (
                        <p className="settings-help">正在加载模型…</p>
                      ) : detail.state === "fail" ? (
                        <p className="settings-help">{detail.message}</p>
                      ) : detail.models.length === 0 ? (
                        <p className="settings-help">
                          {detail.message || "该供应商没有可加载的模型。"}
                        </p>
                      ) : (
                        <ul className="model-detail-list">
                          {detail.models.map((model) => (
                            <li key={model.id}>
                              <span>{model.name}</span>
                              {model.name !== model.id ? (
                                <span className="settings-meta"> {model.id}</span>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
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
            {modelBusy ? "刷新中…" : "刷新状态"}
          </button>
          <button type="button" onClick={() => openSettings("models")}>
            <Settings size={16} strokeWidth={1.75} aria-hidden="true" />
            配置模型
          </button>
        </div>
      </section>

      <section className="settings-card status-tool-card">
        <h3>LCA 工具</h3>
        <div className="status-tool-body">
          <p className="settings-help">
            当前接入 openLCA。之后可以在同一列表切换其他 LCA 工具。
          </p>
          {tools.length ? (
            <>
              <div className="tool-switch" role="tablist" aria-label="LCA 工具">
                {tools.map((tool) => (
                  <button
                    key={tool.id}
                    type="button"
                    role="tab"
                    aria-selected={tool.id === activeTool?.id}
                    onClick={() => setSelectedTool(tool.id)}
                  >
                    {tool.name}
                  </button>
                ))}
              </div>
              {activeTool?.id === "openlca" ? (
                <div className="tool-panel">
                  <ul className="diag-list">
                    <li>
                      <span className={`badge ${activeTool.ok ? "badge-ok" : "badge-warn"}`}>
                        {activeTool.ok ? "可用" : "不可用"}
                      </span>
                      <span>openLCA：{activeTool.message}</span>
                    </li>
                  </ul>
                  <div className="row">
                    <button type="button" onClick={() => openSettings("general")}>
                      端口设置
                    </button>
                  </div>
                </div>
              ) : activeTool ? (
                <div className="tool-panel">
                  <ul className="diag-list">
                    <li>
                      <span className={`badge ${activeTool.ok ? "badge-ok" : "badge-warn"}`}>
                        {activeTool.ok ? "可用" : "不可用"}
                      </span>
                      <span>
                        {activeTool.name}：{activeTool.message}
                      </span>
                    </li>
                  </ul>
                </div>
              ) : null}
            </>
          ) : (
            <p className="settings-help">{loadError ? "诊断未加载" : "正在检查 LCA 工具…"}</p>
          )}
        </div>
        <div className="status-tool-actions">
          <button type="button" onClick={() => void refresh()} disabled={busy}>
            <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
            {busy ? "刷新中…" : "刷新状态"}
          </button>
          <Link href="/plan" className="status-start">
            开始LCA
            <ArrowRight size={16} strokeWidth={1.75} aria-hidden="true" />
          </Link>
        </div>
      </section>
    </div>
  );
}
