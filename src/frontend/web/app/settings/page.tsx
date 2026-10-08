"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type Profile = {
  display_name?: string;
  provider: string;
  model_id: string;
  api_type?: string;
  base_url?: string;
};

type Diagnostics = {
  node: { ok: boolean; message: string };
  pi_agents: { ok: boolean; message: string };
  python_agent: { ok: boolean; message: string };
  openlca: { ok: boolean; message: string };
  profiles: Record<string, Profile>;
  selected_profile?: string;
  credentials?: Record<string, boolean>;
};

type CredInfo = { set: boolean; masked: string | null };
type ProviderCatalogItem = {
  id: string;
  name: string;
  hint: string;
  placeholder: string;
  keys_url?: string;
};

type CredentialsPayload = {
  providers: Record<string, CredInfo>;
  catalog: ProviderCatalogItem[];
};

export default function SettingsPage() {
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [creds, setCreds] = useState<CredentialsPayload | null>(null);
  const [profile, setProfile] = useState("default");
  const [expanded, setExpanded] = useState<string | null>("anthropic");
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [statusMsg, setStatusMsg] = useState("");
  const [statusError, setStatusError] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [envRes, credRes] = await Promise.all([
      fetch("/api/diagnostics/environment"),
      fetch("/api/credentials/status"),
    ]);
    const env = (await envRes.json()) as Diagnostics;
    const credPayload = (await credRes.json()) as CredentialsPayload;
    setDiag(env);
    setCreds(credPayload);
    const selected = env.selected_profile || "default";
    setProfile(selected);
    const selectedProfile = env.profiles?.[selected];
    if (selectedProfile?.provider) {
      setExpanded((prev) => prev ?? selectedProfile.provider);
    }
  }, []);

  useEffect(() => {
    refresh().catch(() => {
      setDiag(null);
      setCreds(null);
    });
  }, [refresh]);

  const profiles = diag?.profiles ?? {
    default: { provider: "anthropic", model_id: "", display_name: "项目默认" },
  };
  const currentProfile = profiles[profile];

  const catalog = useMemo(() => {
    const base = creds?.catalog ?? [];
    const known = new Set(base.map((p) => p.id));
    const extras: ProviderCatalogItem[] = Object.keys(creds?.providers ?? {})
      .filter((id) => !known.has(id))
      .map((id) => ({
        id,
        name: id,
        hint: "已配置的自定义 Provider",
        placeholder: "API key",
      }));
    return [...base, ...extras];
  }, [creds]);

  async function saveModel() {
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await fetch("/api/models/selection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: profile }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || "保存失败");
      }
      setStatusMsg(`已保存默认模型档案：${profile}（立即生效）`);
      await refresh();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveCredential(providerId: string) {
    const apiKey = (draftKeys[providerId] || "").trim();
    if (!apiKey) {
      setStatusError(true);
      setStatusMsg("请填写 API Key");
      return;
    }
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await fetch("/api/credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: providerId, api_key: apiKey }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || "凭证保存失败");
      if (data.providers) {
        setCreds((prev) => ({
          catalog: prev?.catalog ?? [],
          providers: data.providers,
        }));
      }
      setDraftKeys((prev) => ({ ...prev, [providerId]: "" }));
      setStatusMsg(`${providerId} 已保存。新运行立即使用，无需重启。`);
      await refresh();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "凭证保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function clearCredential(providerId: string) {
    if (!window.confirm(`移除 ${providerId} 的 API Key？`)) return;
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await fetch(`/api/credentials/${encodeURIComponent(providerId)}`, {
        method: "DELETE",
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || "清除失败");
      if (data.providers) {
        setCreds((prev) => ({
          catalog: prev?.catalog ?? [],
          providers: data.providers,
        }));
      }
      setStatusMsg(`已清除 ${providerId}`);
      await refresh();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "清除失败");
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await fetch("/api/models/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: profile,
          provider: currentProfile?.provider,
        }),
      });
      const data = await r.json();
      if (data.ok) {
        setStatusMsg(
          `连接成功：${data.provider}/${data.model_id}${data.mode ? ` (${data.mode})` : ""}`,
        );
      } else {
        setStatusError(true);
        setStatusMsg(`连接失败：${data.message || "未知错误"}`);
      }
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "测试失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings-stack">
      <section className="settings-card">
        <h2>设置与初始化</h2>
        <p className="settings-help">
          参考 Pi / BYOK 桌面产品的做法：Worker 固定为 Pi SDK；在下方连接 Provider
          API Key，并选择项目模型档案。密钥只留在本机{" "}
          <span className="mono">.local/credentials/pi-auth.json</span>，不进 Git。
        </p>
        <p className="settings-meta">Changes apply immediately — no restart needed.</p>

        {diag ? (
          <ul className="diag-list">
            <li>
              <span className={`badge ${diag.pi_agents.ok ? "badge-ok" : "badge-warn"}`}>
                {diag.pi_agents.ok ? "就绪" : "未就绪"}
              </span>
              <span>Pi runtime：{diag.pi_agents.message}</span>
            </li>
            <li>
              <span className={`badge ${diag.python_agent.ok ? "badge-ok" : "badge-warn"}`}>
                {diag.python_agent.ok ? "就绪" : "未就绪"}
              </span>
              <span>Python：{diag.python_agent.message}</span>
            </li>
            <li>
              <span className={`badge ${diag.openlca.ok ? "badge-ok" : "badge-warn"}`}>
                {diag.openlca.ok ? "就绪" : "未就绪"}
              </span>
              <span>openLCA：{diag.openlca.message}</span>
            </li>
          </ul>
        ) : (
          <p className="settings-help">加载诊断…</p>
        )}
        <div className="row">
          <button type="button" onClick={() => refresh()} disabled={busy}>
            重新检查环境
          </button>
          <button type="button" className="primary" onClick={testConnection} disabled={busy}>
            测试当前模型连接
          </button>
        </div>
      </section>

      <section className="settings-card">
        <h3>Defaults · 模型档案</h3>
        <p className="settings-help">
          对应 `.env` 的 <span className="mono">PI_MODEL</span>。档案定义在{" "}
          <span className="mono">model_profiles.json</span>；运行时由 Pi{" "}
          <span className="mono">ModelRuntime.getModel(provider, model_id)</span> 解析。
        </p>
        <div className="row">
          <select
            value={profile}
            onChange={(e) => {
              const id = e.target.value;
              setProfile(id);
              const p = profiles[id];
              if (p?.provider) setExpanded(p.provider);
            }}
          >
            {Object.entries(profiles).map(([id, p]) => (
              <option key={id} value={id}>
                {p.display_name ?? id} ({p.provider}/{p.model_id})
              </option>
            ))}
          </select>
          <button type="button" className="primary" onClick={saveModel} disabled={busy}>
            保存默认模型
          </button>
        </div>
        {currentProfile ? (
          <p className="settings-meta">
            当前：{currentProfile.provider}/{currentProfile.model_id}
            {currentProfile.base_url ? ` @ ${currentProfile.base_url}` : ""}
          </p>
        ) : null}
      </section>

      <section className="settings-card">
        <h3>Providers · API keys</h3>
        <p className="settings-help">
          与 k-dense-byok 类似：按 Provider 展开填写密钥。已配置仅显示掩码；会话创建时物化到 Pi{" "}
          <span className="mono">auth.json</span>。
        </p>
        <div className="provider-list">
          {catalog.map((item) => {
            const info = creds?.providers?.[item.id];
            const open = expanded === item.id;
            return (
              <div key={item.id} className="provider-row">
                <button
                  type="button"
                  className="provider-row-head"
                  onClick={() => setExpanded(open ? null : item.id)}
                  aria-expanded={open}
                >
                  <div className="provider-title">
                    <strong>{item.name}</strong>
                    <span>{item.hint}</span>
                  </div>
                  <span className={`badge ${info?.set ? "badge-ok" : "badge-off"}`}>
                    {info?.set ? "已连接" : "未配置"}
                  </span>
                </button>
                {open ? (
                  <div className="provider-body">
                    {info?.set ? (
                      <div className="key-set-line">
                        <span className="badge badge-ok">Key set</span>
                        <span className="mono">{info.masked}</span>
                        <button
                          type="button"
                          className="danger"
                          disabled={busy}
                          onClick={() => clearCredential(item.id)}
                        >
                          清除
                        </button>
                      </div>
                    ) : null}
                    <div className="row">
                      <input
                        type="password"
                        value={draftKeys[item.id] ?? ""}
                        onChange={(e) =>
                          setDraftKeys((prev) => ({ ...prev, [item.id]: e.target.value }))
                        }
                        placeholder={item.placeholder}
                        autoComplete="off"
                        style={{ flex: "1 1 220px" }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void saveCredential(item.id);
                        }}
                      />
                      <button
                        type="button"
                        className="primary"
                        disabled={busy}
                        onClick={() => saveCredential(item.id)}
                      >
                        保存密钥
                      </button>
                      {item.keys_url ? (
                        <a href={item.keys_url} target="_blank" rel="noreferrer">
                          获取密钥
                        </a>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>

      {statusMsg ? (
        <div className={`status-banner${statusError ? " error" : ""}`} role="status">
          {statusMsg}
        </div>
      ) : null}
    </div>
  );
}
