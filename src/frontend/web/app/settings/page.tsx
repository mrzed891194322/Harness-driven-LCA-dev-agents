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

type CredInfo = { set: boolean; masked: string | null; type?: string };
type ProviderCatalogItem = {
  id: string;
  name: string;
  hint: string;
  placeholder: string;
  keys_url?: string;
  supports_oauth?: boolean;
  oauth_label?: string;
  supports_base_url?: boolean;
  default_base_url?: string;
  base_url_hint?: string;
};

type OverrideInfo = {
  base_url?: string | null;
  api?: string | null;
  model_ids?: string[];
  has_api_key?: boolean;
};

type CredentialsPayload = {
  providers: Record<string, CredInfo>;
  catalog: ProviderCatalogItem[];
  overrides?: Record<string, OverrideInfo>;
};

type LoginPrompt = {
  prompt_id?: string;
  prompt?: {
    type?: string;
    message?: string;
    placeholder?: string;
    options?: { id: string; label: string; description?: string }[];
  };
};

export default function SettingsPage() {
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [creds, setCreds] = useState<CredentialsPayload | null>(null);
  const [profile, setProfile] = useState("default");
  const [expanded, setExpanded] = useState<string | null>("anthropic");
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [draftBaseUrls, setDraftBaseUrls] = useState<Record<string, string>>({});
  const [statusMsg, setStatusMsg] = useState("");
  const [statusError, setStatusError] = useState(false);
  const [busy, setBusy] = useState(false);

  const [loginId, setLoginId] = useState<string | null>(null);
  const [loginProvider, setLoginProvider] = useState<string | null>(null);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<LoginPrompt | null>(null);
  const [promptValue, setPromptValue] = useState("");

  const [customForm, setCustomForm] = useState({
    profile_id: "local-ollama",
    provider: "ollama",
    base_url: "http://localhost:11434/v1",
    api_type: "openai-completions",
    model_id: "qwen2.5-coder:7b",
    display_name: "本地 Ollama",
    api_key: "ollama",
  });

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
    const urls: Record<string, string> = {};
    for (const [id, ov] of Object.entries(credPayload.overrides ?? {})) {
      if (ov.base_url) urls[id] = ov.base_url;
    }
    setDraftBaseUrls((prev) => ({ ...urls, ...prev }));
  }, []);

  useEffect(() => {
    refresh().catch(() => {
      setDiag(null);
      setCreds(null);
    });
  }, [refresh]);

  useEffect(() => {
    if (!loginId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const r = await fetch(`/api/credentials/oauth/${encodeURIComponent(loginId)}`);
        const data = await r.json();
        if (!r.ok || cancelled) return;
        for (const ev of data.events ?? []) {
          if (ev.kind === "notify" && ev.event?.type === "auth_url" && ev.event?.url) {
            setAuthUrl(String(ev.event.url));
          }
        }
        if (data.pending_prompt?.prompt_id) {
          setPendingPrompt(data.pending_prompt);
        } else {
          setPendingPrompt(null);
        }
        if (data.done) {
          setLoginId(null);
          setLoginProvider(null);
          if (data.ok) {
            setStatusError(false);
            setStatusMsg(`${data.provider} OAuth 登录成功`);
            setAuthUrl(null);
            setPendingPrompt(null);
            await refresh();
          } else {
            setStatusError(true);
            setStatusMsg(`OAuth 失败：${data.error || "未知错误"}`);
          }
        }
      } catch {
        /* ignore transient poll errors */
      }
    };
    const id = window.setInterval(() => void tick(), 800);
    void tick();
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [loginId, refresh]);

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
        supports_base_url: true,
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
          overrides: data.overrides ?? prev?.overrides,
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
    if (!window.confirm(`移除 ${providerId} 的凭证？`)) return;
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const info = creds?.providers?.[providerId];
      if (info?.type === "oauth") {
        const r = await fetch("/api/credentials/oauth/logout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: providerId }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || "退出登录失败");
      } else {
        const r = await fetch(`/api/credentials/${encodeURIComponent(providerId)}`, {
          method: "DELETE",
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || "清除失败");
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

  async function startOAuth(providerId: string) {
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    setAuthUrl(null);
    setPendingPrompt(null);
    setPromptValue("");
    try {
      const r = await fetch("/api/credentials/oauth/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: providerId, auth_type: "oauth" }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || "无法启动 OAuth");
      setLoginId(String(data.login_id));
      setLoginProvider(providerId);
      setStatusMsg(`正在登录 ${providerId}（Pi ModelRuntime.login）…`);
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "OAuth 启动失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitPromptReply() {
    if (!loginId || !pendingPrompt?.prompt_id) return;
    setBusy(true);
    try {
      const r = await fetch("/api/credentials/oauth/reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          login_id: loginId,
          prompt_id: pendingPrompt.prompt_id,
          value: promptValue,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || "提交失败");
      setPromptValue("");
      setPendingPrompt(null);
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveBaseUrl(providerId: string) {
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await fetch("/api/credentials/base-url", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: providerId,
          base_url: (draftBaseUrls[providerId] || "").trim(),
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || "保存失败");
      setStatusMsg(
        data.base_url
          ? `${providerId} baseUrl 已保存（Pi models.json）`
          : `${providerId} 已清除自定义 URL，将使用 Pi 默认 baseUrl`,
      );
      await refresh();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveCustomEndpoint() {
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await fetch("/api/models/custom-endpoint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...customForm, set_as_default: true }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || "保存失败");
      setStatusMsg(`已保存自定义端点档案 ${customForm.profile_id}（Pi compatible endpoint）`);
      await refresh();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "保存失败");
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
          Worker 固定为 Pi SDK（ModelRuntime）。凭证写入{" "}
          <span className="mono">.local/credentials/pi-auth.json</span>；供应商 URL / 兼容端点写入{" "}
          <span className="mono">pi-models.json</span>（Pi{" "}
          <span className="mono">models.json</span> 形态）。不进 Git。
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
          对应 <span className="mono">PI_MODEL</span>。内置档案在{" "}
          <span className="mono">model_profiles.json</span>；自定义端点档案在{" "}
          <span className="mono">.local/model_profiles.json</span>。
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
            {currentProfile.api_type ? ` · ${currentProfile.api_type}` : ""}
          </p>
        ) : null}
      </section>

      <section className="settings-card">
        <h3>Providers · API keys / OAuth</h3>
        <p className="settings-help">
          API Key 写入 Pi <span className="mono">auth.json</span>。OpenAI Auth 走 Pi 内置{" "}
          <span className="mono">openaiChatGPTOAuth</span>（与 TUI{" "}
          <span className="mono">LoginDialogComponent</span> 同一{" "}
          <span className="mono">ModelRuntime.login(..., &apos;oauth&apos;, AuthInteraction)</span>
          ）。本机回调 <span className="mono">http://127.0.0.1:1455/auth/callback</span>
          ；远程请粘贴浏览器最终跳转 URL。
        </p>
        {(loginId || authUrl || pendingPrompt) && (
          <div className="oauth-panel">
            <p className="settings-meta">
              Pi OAuth 进行中{loginProvider ? `：${loginProvider}` : ""}
              {loginProvider === "openai" ? "（Sign in with ChatGPT）" : ""}
            </p>
            {authUrl ? (
              <p className="settings-help">
                打开授权页：{" "}
                <a href={authUrl} target="_blank" rel="noreferrer">
                  {authUrl}
                </a>
              </p>
            ) : null}
            {pendingPrompt?.prompt ? (
              <div style={{ marginTop: 8 }}>
                <p className="settings-help">{pendingPrompt.prompt.message}</p>
                {pendingPrompt.prompt.type === "select" && pendingPrompt.prompt.options?.length ? (
                  <div className="row">
                    {pendingPrompt.prompt.options.map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          setPromptValue(opt.id);
                          void (async () => {
                            if (!loginId || !pendingPrompt.prompt_id) return;
                            setBusy(true);
                            try {
                              const r = await fetch("/api/credentials/oauth/reply", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                  login_id: loginId,
                                  prompt_id: pendingPrompt.prompt_id,
                                  value: opt.id,
                                }),
                              });
                              const data = await r.json().catch(() => ({}));
                              if (!r.ok) throw new Error(data.detail || "提交失败");
                              setPendingPrompt(null);
                              setPromptValue("");
                            } catch (e) {
                              setStatusError(true);
                              setStatusMsg(e instanceof Error ? e.message : "提交失败");
                            } finally {
                              setBusy(false);
                            }
                          })();
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="row">
                    <input
                      type={pendingPrompt.prompt.type === "secret" ? "password" : "text"}
                      value={promptValue}
                      onChange={(e) => setPromptValue(e.target.value)}
                      placeholder={
                        pendingPrompt.prompt.placeholder ||
                        (pendingPrompt.prompt.type === "manual_code"
                          ? "http://127.0.0.1:1455/auth/callback?code=…&state=…"
                          : "按提示输入")
                      }
                      style={{ flex: "1 1 240px" }}
                    />
                    <button
                      type="button"
                      className="primary"
                      disabled={busy}
                      onClick={submitPromptReply}
                    >
                      提交
                    </button>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}
        <div className="provider-list">
          {catalog.map((item) => {
            const info = creds?.providers?.[item.id];
            const open = expanded === item.id;
            const override = creds?.overrides?.[item.id];
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
                    {info?.set
                      ? info.type === "oauth"
                        ? "OAuth"
                        : "已连接"
                      : "未配置"}
                  </span>
                </button>
                {open ? (
                  <div className="provider-body">
                    {info?.set ? (
                      <div className="key-set-line">
                        <span className="badge badge-ok">
                          {info.type === "oauth" ? "OAuth set" : "Key set"}
                        </span>
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
                      {item.supports_oauth ? (
                        <button
                          type="button"
                          disabled={busy || Boolean(loginId)}
                          onClick={() => startOAuth(item.id)}
                        >
                          {item.oauth_label || "Auth 登录"}
                        </button>
                      ) : null}
                      {item.keys_url ? (
                        <a href={item.keys_url} target="_blank" rel="noreferrer">
                          获取密钥
                        </a>
                      ) : null}
                    </div>
                    {item.supports_base_url !== false ? (
                      <div style={{ marginTop: 10 }}>
                        <div className="row">
                          <input
                            type="url"
                            value={draftBaseUrls[item.id] ?? override?.base_url ?? ""}
                            onChange={(e) =>
                              setDraftBaseUrls((prev) => ({
                                ...prev,
                                [item.id]: e.target.value,
                              }))
                            }
                            placeholder={
                              item.default_base_url
                                ? `留空 = ${item.default_base_url}`
                                : "留空 = Pi 默认 baseUrl"
                            }
                            style={{ flex: "1 1 260px" }}
                          />
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => saveBaseUrl(item.id)}
                          >
                            保存 URL
                          </button>
                        </div>
                        <p className="settings-meta" style={{ marginTop: 6 }}>
                          {override?.base_url
                            ? `当前覆盖：${override.base_url}`
                            : `当前：Pi 默认${item.default_base_url ? `（${item.default_base_url}）` : ""}`}
                          {item.base_url_hint ? ` · ${item.base_url_hint}` : ""}
                        </p>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>

      <section className="settings-card">
        <h3>自定义 API / 本地模型</h3>
        <p className="settings-help">
          使用 Pi 文档 compatible endpoint（Ollama、LM Studio、vLLM、自建网关）：写入{" "}
          <span className="mono">pi-models.json</span>。
          <span className="mono">openai-completions</span> /{" "}
          <span className="mono">openai-responses</span> 通常需要{" "}
          <span className="mono">/v1</span> 后缀（例{" "}
          <span className="mono">http://localhost:11434/v1</span>）；
          <span className="mono">anthropic-messages</span> 一般不加{" "}
          <span className="mono">/v1</span>。
        </p>
        <div className="custom-grid">
          <label>
            档案 id
            <input
              value={customForm.profile_id}
              onChange={(e) => setCustomForm((p) => ({ ...p, profile_id: e.target.value }))}
            />
          </label>
          <label>
            Provider id
            <input
              value={customForm.provider}
              onChange={(e) => setCustomForm((p) => ({ ...p, provider: e.target.value }))}
            />
          </label>
          <label>
            Base URL
            <input
              value={customForm.base_url}
              onChange={(e) => setCustomForm((p) => ({ ...p, base_url: e.target.value }))}
            />
          </label>
          <label>
            API 类型
            <select
              value={customForm.api_type}
              onChange={(e) => setCustomForm((p) => ({ ...p, api_type: e.target.value }))}
            >
              <option value="openai-completions">openai-completions</option>
              <option value="openai-responses">openai-responses</option>
              <option value="anthropic-messages">anthropic-messages</option>
              <option value="google-generative-ai">google-generative-ai</option>
            </select>
          </label>
          <label>
            Model id
            <input
              value={customForm.model_id}
              onChange={(e) => setCustomForm((p) => ({ ...p, model_id: e.target.value }))}
            />
          </label>
          <label>
            显示名
            <input
              value={customForm.display_name}
              onChange={(e) => setCustomForm((p) => ({ ...p, display_name: e.target.value }))}
            />
          </label>
          <label>
            apiKey（本地可填占位）
            <input
              value={customForm.api_key}
              onChange={(e) => setCustomForm((p) => ({ ...p, api_key: e.target.value }))}
            />
          </label>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <button type="button" className="primary" disabled={busy} onClick={saveCustomEndpoint}>
            保存并设为默认
          </button>
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
