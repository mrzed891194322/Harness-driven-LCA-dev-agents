"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

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

type CustomEndpoint = {
  profile_id: string;
  provider: string;
  base_url: string;
  api_type: string;
  model_id: string;
  display_name: string;
  has_api_key: boolean;
};

type CustomForm = {
  profile_id: string;
  provider: string;
  base_url: string;
  api_type: string;
  model_id: string;
  display_name: string;
  api_key: string;
  previous_profile_id: string;
  previous_provider: string;
  previous_model_id: string;
};

const EMPTY_CUSTOM_FORM: CustomForm = {
  profile_id: "",
  provider: "",
  base_url: "",
  api_type: "openai-completions",
  model_id: "",
  display_name: "",
  api_key: "",
  previous_profile_id: "",
  previous_provider: "",
  previous_model_id: "",
};

function endpointKey(item: CustomEndpoint): string {
  return item.profile_id || `${item.provider}/${item.model_id}`;
}

type LoginPrompt = {
  prompt_id?: string;
  prompt?: {
    type?: string;
    message?: string;
    placeholder?: string;
    options?: { id: string; label: string; description?: string }[];
  };
};

export function ModelsSection({ onChanged }: { onChanged?: () => void }) {
  const [creds, setCreds] = useState<CredentialsPayload | null>(null);
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
  const [customEndpoints, setCustomEndpoints] = useState<CustomEndpoint[]>([]);
  const [addingCustom, setAddingCustom] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [customForm, setCustomForm] = useState<CustomForm>(EMPTY_CUSTOM_FORM);

  const refresh = useCallback(async () => {
    const [credRes, customRes] = await Promise.all([
      fetch("/api/credentials/status"),
      fetch("/api/models/custom-endpoints"),
    ]);
    const credPayload = (await credRes.json()) as CredentialsPayload;
    if (!credRes.ok || !Array.isArray(credPayload?.catalog)) {
      throw new Error(`模型配置不可用（HTTP ${credRes.status}）。请确认后端已启动。`);
    }
    setCreds(credPayload);
    if (customRes.ok) {
      const customPayload = (await customRes.json()) as { endpoints?: CustomEndpoint[] };
      setCustomEndpoints(Array.isArray(customPayload.endpoints) ? customPayload.endpoints : []);
    }
    const urls: Record<string, string> = {};
    for (const [id, ov] of Object.entries(credPayload?.overrides ?? {})) {
      if (ov.base_url) urls[id] = ov.base_url;
    }
    setDraftBaseUrls((prev) => ({ ...urls, ...prev }));
  }, []);

  useEffect(() => {
    refresh().catch((error: unknown) => {
      setStatusError(true);
      setStatusMsg(error instanceof Error ? error.message : "加载模型配置失败");
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
            onChanged?.();
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
  }, [loginId, onChanged, refresh]);

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
      onChanged?.();
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
      onChanged?.();
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

  async function submitPromptReply(value = promptValue) {
    if (!loginId || !pendingPrompt?.prompt_id) return;
    setBusy(true);
    try {
      const r = await fetch("/api/credentials/oauth/reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          login_id: loginId,
          prompt_id: pendingPrompt.prompt_id,
          value,
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
      onChanged?.();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveCustomEndpoint() {
    const profileId = customForm.profile_id.trim();
    const provider = customForm.provider.trim();
    const baseUrl = customForm.base_url.trim();
    const modelId = customForm.model_id.trim();
    if (!profileId || !provider || !baseUrl || !modelId) {
      setStatusError(true);
      setStatusMsg("请填写端点 id、Provider id、Base URL 和 Model id");
      return;
    }
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await fetch("/api/models/custom-endpoint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...customForm, profile_id: profileId, provider, base_url: baseUrl, model_id: modelId }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || "保存失败");
      if (Array.isArray(data.endpoints)) setCustomEndpoints(data.endpoints);
      setStatusMsg(`已保存自定义端点 ${profileId}`);
      setCustomForm(EMPTY_CUSTOM_FORM);
      setAddingCustom(false);
      setEditingKey(null);
      await refresh();
      onChanged?.();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  function renderCustomForm(onCancel: () => void) {
    const editing = Boolean(customForm.previous_provider || customForm.previous_profile_id);
    return (
      <>
        <div className="custom-grid">
          <label>
            端点 id
            <input
              value={customForm.profile_id}
              placeholder="local-ollama"
              onChange={(e) => setCustomForm((p) => ({ ...p, profile_id: e.target.value }))}
            />
          </label>
          <label>
            Provider id
            <input
              value={customForm.provider}
              placeholder="ollama"
              onChange={(e) => setCustomForm((p) => ({ ...p, provider: e.target.value }))}
            />
          </label>
          <label>
            Base URL
            <input
              value={customForm.base_url}
              placeholder="http://localhost:11434/v1"
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
              placeholder="qwen2.5-coder:7b"
              onChange={(e) => setCustomForm((p) => ({ ...p, model_id: e.target.value }))}
            />
          </label>
          <label>
            显示名
            <input
              value={customForm.display_name}
              placeholder="本地 Ollama"
              onChange={(e) => setCustomForm((p) => ({ ...p, display_name: e.target.value }))}
            />
          </label>
          <label>
            apiKey（本地可填占位）
            <input
              value={customForm.api_key}
              placeholder={editing ? "留空则保留已有密钥" : "留空则写入 local"}
              onChange={(e) => setCustomForm((p) => ({ ...p, api_key: e.target.value }))}
            />
          </label>
        </div>
        <div className="row">
          <button type="button" className="primary" disabled={busy} onClick={() => void saveCustomEndpoint()}>
            保存端点
          </button>
          <button type="button" disabled={busy} onClick={onCancel}>
            取消
          </button>
        </div>
      </>
    );
  }

  return (
    <div className="settings-section">
      <p className="settings-help">
        配置 Provider 密钥与自定义端点。已配置的供应商会出现在状态页的模型可用性中。凭证写入{" "}
        <span className="mono">.local/credentials/pi-auth.json</span>，不进 Git。
      </p>

        <section className="settings-card">
          <h3>Providers</h3>
          <p className="settings-help">
            API Key 写入 Pi <span className="mono">auth.json</span>。OpenAI Auth 走 Pi 内置{" "}
            <span className="mono">openaiChatGPTOAuth</span>。本机回调{" "}
            <span className="mono">http://127.0.0.1:1455/auth/callback</span>
            ；远程请粘贴浏览器最终跳转 URL。
          </p>
          {(loginId || authUrl || pendingPrompt) && (
            <div className="oauth-panel">
              <p className="settings-meta">
                Pi OAuth 进行中{loginProvider ? `：${loginProvider}` : ""}
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
                          onClick={() => void submitPromptReply(opt.id)}
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
                        onClick={() => void submitPromptReply()}
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
              const rowOpen = expanded === item.id;
              const override = creds?.overrides?.[item.id];
              return (
                <div key={item.id} className="provider-row">
                  <button
                    type="button"
                    className="provider-row-head"
                    onClick={() => setExpanded(rowOpen ? null : item.id)}
                    aria-expanded={rowOpen}
                  >
                    <div className="provider-title">
                      <strong>{item.name}</strong>
                      <span>{item.hint}</span>
                    </div>
                    <span className={`badge ${info?.set ? "badge-ok" : "badge-off"}`}>
                      {info?.set ? (info.type === "oauth" ? "OAuth" : "已连接") : "未配置"}
                    </span>
                  </button>
                  {rowOpen ? (
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
            可保存多个兼容端点（Ollama、LM Studio、vLLM、自建网关）。已保存的端点会保留；新端点请使用新的 Provider id。同一 Provider id 下的模型共用 Base URL 和密钥。
          </p>
          {customEndpoints.length ? (
            <ul className="custom-saved">
              {customEndpoints.map((item) => {
                const key = endpointKey(item);
                const editing = editingKey === key;
                return (
                  <li key={key}>
                    <div className="custom-saved-head">
                      <strong>{item.display_name || item.model_id}</strong>
                      <span className="custom-saved-actions">
                        <span className="badge badge-ok">已保存</span>
                        <button
                          type="button"
                          disabled={busy || editing}
                          onClick={() => {
                            setAddingCustom(false);
                            setEditingKey(key);
                            setCustomForm({
                              profile_id: item.profile_id,
                              provider: item.provider,
                              base_url: item.base_url,
                              api_type: item.api_type || "openai-completions",
                              model_id: item.model_id,
                              display_name: item.display_name,
                              api_key: "",
                              previous_profile_id: item.profile_id,
                              previous_provider: item.provider,
                              previous_model_id: item.model_id,
                            });
                          }}
                        >
                          编辑
                        </button>
                      </span>
                    </div>
                    {editing ? (
                      renderCustomForm(() => {
                        setEditingKey(null);
                        setCustomForm(EMPTY_CUSTOM_FORM);
                      })
                    ) : (
                      <>
                        <p className="settings-meta">
                          {item.profile_id ? `${item.profile_id} · ` : ""}
                          {item.provider}/{item.model_id}
                          {item.api_type ? ` · ${item.api_type}` : ""}
                        </p>
                        {item.base_url ? <p className="settings-meta">{item.base_url}</p> : null}
                        <p className="settings-meta">{item.has_api_key ? "密钥已保存" : "未保存密钥"}</p>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="settings-help">还没有自定义模型。</p>
          )}
          <div className="row">
            <button
              type="button"
              onClick={() => {
                setEditingKey(null);
                setCustomForm(EMPTY_CUSTOM_FORM);
                setAddingCustom(true);
              }}
              disabled={addingCustom}
            >
              添加新自定义模型
            </button>
          </div>
          {addingCustom ? (
            <div className="custom-panel">
              {renderCustomForm(() => {
                setAddingCustom(false);
                setCustomForm(EMPTY_CUSTOM_FORM);
              })}
            </div>
          ) : null}
        </section>

        {statusMsg ? (
          <div className={`status-banner${statusError ? " error" : ""}`} role="status">
            {statusMsg}
          </div>
        ) : null}
    </div>
  );
}
