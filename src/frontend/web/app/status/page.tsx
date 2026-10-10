"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Bot, Cpu, List, RefreshCw, Save, Settings, Wrench } from "lucide-react";
import Link from "next/link";
import { useSettings } from "../../components/settings/settings-context";
import { apiFetch } from "../../lib/api";

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

function statusProviderName(provider: AvailableProvider): string {
  if (provider.id === "openai") return "OpenAI";
  return provider.name;
}

function OpenLcaToolPanel({ tool, onSaved }: { tool: LcaTool; onSaved: () => Promise<void> }) {
  const [portDraft, setPortDraft] = useState(tool.port != null ? String(tool.port) : "");
  const [portBusy, setPortBusy] = useState(false);
  const [portError, setPortError] = useState("");

  useEffect(() => {
    if (tool.port != null) setPortDraft(String(tool.port));
  }, [tool.port]);

  async function savePort() {
    const port = Number(portDraft);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      setPortError("端口须为 1–65535 的整数");
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
      if (!response.ok) throw new Error(data.detail || "保存端口失败");
      await onSaved();
    } catch (error: unknown) {
      setPortError(error instanceof Error ? error.message : "保存端口失败");
    } finally {
      setPortBusy(false);
    }
  }

  return (
    <div className="tool-panel">
      <div className="tool-port-row">
        <label htmlFor="openlca-port">IPC端口</label>
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
          {portBusy ? "保存中…" : "保存"}
        </button>
      </div>
      {portError ? <p className="settings-help">{portError}</p> : null}
      <div className="tool-status-row">
        <span>当前状态</span>
        <span className={`badge ${tool.ok ? "badge-ok" : "badge-warn"}`}>
          {tool.ok ? "可用" : "不可用"}
        </span>
      </div>
    </div>
  );
}

function ToolConnectionPanel({ tool, onOpenLcaSaved }: { tool: LcaTool; onOpenLcaSaved: () => Promise<void> }) {
  if (tool.id === "openlca") return <OpenLcaToolPanel tool={tool} onSaved={onOpenLcaSaved} />;
  return (
    <div className="tool-panel">
      <div className="tool-status-row">
        <span>当前状态</span>
        <span className={`badge ${tool.ok ? "badge-ok" : "badge-warn"}`}>
          {tool.ok ? "可用" : "不可用"}
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
      const envRes = await apiFetch("/api/diagnostics/environment");
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
      const response = await apiFetch("/api/models/providers");
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

  const typescriptReady = Boolean(diag?.node.ok);
  const pythonReady = Boolean(diag?.python_agent.ok);
  const environments = [
    {
      id: "typescript",
      title: "TypeScript",
      ready: typescriptReady,
      message: diag?.node.message || "",
      tools: [
        { name: "TypeScript", version: "5.9.3", note: "前端与运行时语言", src: "/toolchain/typescript.svg" },
        { name: "npm", version: "11.19.1", note: "安装依赖并启动", src: "/toolchain/npm.svg" },
        { name: "Pi SDK", version: "1.1.0", note: "代理运行时", src: "/toolchain/pi.svg" },
        { name: "Next.js", version: "15.5.27", note: "控制面板页面", src: "/toolchain/next.svg" },
      ],
    },
    {
      id: "python",
      title: "Python",
      ready: pythonReady,
      message: diag?.python_agent.message || "",
      tools: [
        { name: "Python", version: "3.12.12", note: "后端解释器", src: "/toolchain/python.svg" },
        { name: "uv", version: "0.9.26", note: "管理 Python 依赖", src: "/toolchain/uv.svg" },
      ],
    },
  ];

  return (
    <div className="status-board">
      <section className="settings-card status-runtime-card">
        <h3>
          <Cpu size={18} strokeWidth={1.75} aria-hidden="true" />
          项目环境
        </h3>
        {diag ? (
          <div className="status-env-list">
            {environments.map((env) => (
              <section key={env.id} className="status-env">
                <header className="status-env-head">
                  <strong>{env.title}</strong>
                  <span className={`badge ${env.ready ? "badge-ok" : "badge-warn"}`}>
                    {env.ready ? "就绪" : "未就绪"}
                  </span>
                </header>
                {env.ready ? (
                  <ul className="status-toolchain">
                    {env.tools.map((tool) => (
                      <li key={tool.name}>
                        <img src={tool.src} alt="" />
                        <strong>{tool.name}</strong>
                        <span className="status-tool-version">{tool.version}</span>
                        <span className="status-tool-note">{tool.note}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="settings-help">{env.message || "环境未就绪"}</p>
                )}
              </section>
            ))}
          </div>
        ) : (
          <p className="settings-help">{loadError || "正在检查运行时…"}</p>
        )}
        <div className="status-runtime-actions">
          <button type="button" onClick={() => void refresh()} disabled={busy}>
            <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
            {busy ? "检查中…" : "重新检查"}
          </button>
          <button type="button" onClick={() => openSettings("general")}>
            <Settings size={16} strokeWidth={1.75} aria-hidden="true" />
            配置项目
          </button>
        </div>
      </section>

      <section className="settings-card status-model-card">
        <h3>
          <Bot size={18} strokeWidth={1.75} aria-hidden="true" />
          模型可用性
        </h3>
        {providers === null ? (
          <p className="settings-help">{providerError || "正在检查供应商…"}</p>
        ) : providerRows.length === 0 ? (
          <p className="settings-help">
            {providerError || "还没有可用供应商。请在设置中配置模型。"}
          </p>
        ) : (
          <>
            <h4 className="status-provider-label">已配置供应商</h4>
            <ul className="status-model-body diag-list">
            {providerRows.map((provider) => {
              const open = openProvider === provider.id;
              const detail = modelLists[provider.id];
              return (
                <li key={provider.id} className="status-provider">
                  <div className="status-provider-head">
                    <span className="status-provider-dot" role="img" aria-label="已连接" />
                    <span>{statusProviderName(provider)}</span>
                    <button
                      type="button"
                      aria-expanded={open}
                      onClick={() => void toggleProvider(provider.id)}
                    >
                      <List size={14} strokeWidth={1.75} aria-hidden="true" />
                      {open ? "收起" : "模型列表"}
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
            {modelBusy ? "刷新中…" : "刷新状态"}
          </button>
          <button type="button" onClick={() => openSettings("models")}>
            <Settings size={16} strokeWidth={1.75} aria-hidden="true" />
            配置模型
          </button>
        </div>
      </section>

      <section className="settings-card status-tool-card">
        <h3>
          <Wrench size={18} strokeWidth={1.75} aria-hidden="true" />
          LCA 工具
        </h3>
        <div className="status-tool-body">
          <h4 className="status-provider-label">当前工具</h4>
          {tools.length ? (
            <>
              <div className="tool-switch-row">
                <div className="tool-switch" role="tablist" aria-label="LCA 工具">
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
                          <span>生命周期建模与计算</span>
                        </>
                      ) : (
                        tool.name
                      )}
                    </button>
                  ))}
                </div>
                <p className="tool-switch-pending">其他 LCA 工具集成开发中</p>
              </div>
              {activeTool ? (
                <ToolConnectionPanel key={activeTool.id} tool={activeTool} onOpenLcaSaved={refresh} />
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
