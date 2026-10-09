"use client";

import { useCallback, useEffect, useState } from "react";
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

type ModelStatus = {
  profile_id: string;
  display_name: string;
  provider: string;
  model_id: string;
  base_url?: string;
  credential_set: boolean;
};

type Diagnostics = {
  node: Check;
  pi_agents: Check;
  python_agent: Check;
  openlca: Check & { host?: string; port?: number };
  lca_tools?: LcaTool[];
  model?: ModelStatus;
  profiles?: Record<string, { display_name?: string; provider: string; model_id: string; base_url?: string }>;
  selected_profile?: string;
  credentials?: Record<string, boolean>;
};

type Probe = { state: "idle" | "ok" | "fail"; message: string };

function isDiagnostics(value: unknown): value is Diagnostics {
  if (!value || typeof value !== "object") return false;
  const row = value as Diagnostics;
  return Boolean(row.pi_agents && row.python_agent && row.openlca && "ok" in row.pi_agents);
}

function modelFromDiag(diag: Diagnostics): ModelStatus {
  if (diag.model?.profile_id) return diag.model;
  const id = diag.selected_profile || "default";
  const profile = diag.profiles?.[id];
  const provider = profile?.provider || "";
  return {
    profile_id: id,
    display_name: profile?.display_name || id,
    provider,
    model_id: profile?.model_id || "",
    base_url: profile?.base_url,
    credential_set: Boolean(provider && diag.credentials?.[provider]),
  };
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
  const [probe, setProbe] = useState<Probe>({ state: "idle", message: "" });
  const [selectedTool, setSelectedTool] = useState("openlca");

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

  useEffect(() => {
    if (revision > 0) setProbe({ state: "idle", message: "" });
    void refresh();
  }, [refresh, revision]);

  useEffect(() => {
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  const model = diag ? modelFromDiag(diag) : null;
  const tools = diag ? toolsFromDiag(diag) : [];
  const activeTool = tools.find((tool) => tool.id === selectedTool) ?? tools[0];

  async function checkModel() {
    if (!model) return;
    setBusy(true);
    setProbe({ state: "idle", message: "正在检查模型连接…" });
    try {
      const r = await fetch("/api/models/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: model.profile_id,
          provider: model.provider,
        }),
      });
      const data = await r.json();
      if (data.ok) {
        setProbe({
          state: "ok",
          message: `可用：${data.provider}/${data.model_id}${data.mode ? ` (${data.mode})` : ""}`,
        });
      } else {
        setProbe({ state: "fail", message: data.message || "连接失败" });
      }
    } catch (error: unknown) {
      setProbe({
        state: "fail",
        message: error instanceof Error ? error.message : "检查失败",
      });
    } finally {
      setBusy(false);
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

      <section className="settings-card">
        <div className="section-head">
          <h3>模型可用性</h3>
          <button type="button" onClick={() => openSettings("models")}>
            配置模型
          </button>
        </div>
        {model ? (
          <>
            <ul className="diag-list">
              <li>
                <span className="badge badge-off">档案</span>
                <span>
                  {model.display_name}
                  <span className="settings-meta"> · {model.profile_id}</span>
                </span>
              </li>
              <li>
                <span className={`badge ${model.provider && model.model_id ? "badge-ok" : "badge-warn"}`}>
                  模型
                </span>
                <span>
                  {model.provider && model.model_id
                    ? `${model.provider}/${model.model_id}`
                    : "未解析到模型"}
                  {model.base_url ? ` @ ${model.base_url}` : ""}
                </span>
              </li>
              <li>
                <span className={`badge ${model.credential_set ? "badge-ok" : "badge-warn"}`}>
                  {model.credential_set ? "已配置" : "未配置"}
                </span>
                <span>
                  凭证：
                  {model.credential_set
                    ? `${model.provider} 已有密钥或 OAuth`
                    : `${model.provider || "当前 Provider"} 尚未配置`}
                </span>
              </li>
              <li>
                <span
                  className={`badge ${
                    probe.state === "ok"
                      ? "badge-ok"
                      : probe.state === "fail"
                        ? "badge-warn"
                        : "badge-off"
                  }`}
                >
                  {probe.state === "ok" ? "可用" : probe.state === "fail" ? "不可用" : "未检查"}
                </span>
                <span>连接：{probe.message || "尚未探测连接"}</span>
              </li>
            </ul>
            <div className="row">
              <button type="button" className="primary" onClick={() => void checkModel()} disabled={busy}>
                检查可用性
              </button>
            </div>
          </>
        ) : (
          <p className="settings-help">{loadError ? "诊断未加载" : "正在读取模型档案…"}</p>
        )}
      </section>

      <section className="settings-card">
        <h3>LCA 工具</h3>
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
      </section>

      <div className="status-board-action">
        <Link href="/plan" className="status-start">
          开始LCA
        </Link>
      </div>
    </div>
  );
}
