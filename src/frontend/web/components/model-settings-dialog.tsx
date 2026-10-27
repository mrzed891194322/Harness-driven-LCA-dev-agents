"use client";

import { useLocale } from "../lib/i18n/locale-context";
import { Copy, Pencil, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../lib/api";

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

const PROVIDER_RANK = ["openai", "anthropic", "deepseek"];
const NO_BASE_URL = new Set(["deepseek", "google"]);

function providerRank(id: string): number {
  const index = PROVIDER_RANK.indexOf(id);
  if (index !== -1) return index;
  if (id === "opencode-go") return 1000;
  return PROVIDER_RANK.length;
}

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
  const { t } = useLocale();
  const [creds, setCreds] = useState<CredentialsPayload | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
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
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [customForm, setCustomForm] = useState<CustomForm>(EMPTY_CUSTOM_FORM);

  const refresh = useCallback(async () => {
    const [credRes, customRes] = await Promise.all([
      apiFetch("/api/credentials/status"),
      apiFetch("/api/models/custom-endpoints"),
    ]);
    const credPayload = (await credRes.json()) as CredentialsPayload;
    if (!credRes.ok || !Array.isArray(credPayload?.catalog)) {
      throw new Error(t("models.configUnavailable", { status: credRes.status }));
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
      setStatusMsg(error instanceof Error ? error.message : t("models.loadFail"));
    });
  }, [refresh]);

  useEffect(() => {
    if (!loginId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const r = await apiFetch(`/api/credentials/oauth/${encodeURIComponent(loginId)}`);
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
            setStatusMsg(t("models.oauthOk", { provider: data.provider }));
            setAuthUrl(null);
            setPendingPrompt(null);
            await refresh();
            onChanged?.();
          } else {
            setStatusError(true);
            setStatusMsg(t("models.oauthFailDetail", { error: data.error || t("common.unknownError") }));
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
        hint: t("models.customProviders"),
        placeholder: "API key",
        supports_base_url: true,
      }));
    const items = [...base, ...extras].map((item) => {
      if (NO_BASE_URL.has(item.id)) return { ...item, supports_base_url: false };
      if (item.id === "anthropic") {
        return {
          ...item,
          base_url_hint: t("models.hostHint"),
        };
      }
      if (item.id === "openai") {
        return {
          ...item,
          name: "OpenAI",
          hint: t("models.authKeyOrOauth"),
          base_url_hint: t("models.v1Hint"),
        };
      }
      return item;
    });
    const original = new Map(items.map((item, index) => [item.id, index]));
    items.sort(
      (a, b) => providerRank(a.id) - providerRank(b.id) || (original.get(a.id) ?? 0) - (original.get(b.id) ?? 0),
    );
    return items;
  }, [creds]);

  async function saveCredential(providerId: string) {
    const apiKey = (draftKeys[providerId] || "").trim();
    if (!apiKey) {
      setStatusError(true);
      setStatusMsg(t("models.needApiKey"));
      return;
    }
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await apiFetch("/api/credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: providerId, api_key: apiKey }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || t("models.credSaveFail"));
      if (data.providers) {
        setCreds((prev) => ({
          catalog: prev?.catalog ?? [],
          providers: data.providers,
          overrides: data.overrides ?? prev?.overrides,
        }));
      }
      setDraftKeys((prev) => ({ ...prev, [providerId]: "" }));
      const replacedOAuth = creds?.providers?.[providerId]?.type === "oauth";
      setStatusMsg(
        replacedOAuth && providerId === "openai"
          ? t("models.openaiSaved")
          : t("models.savedRestart", { id: providerId }),
      );
      await refresh();
      onChanged?.();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : t("models.credSaveFail"));
    } finally {
      setBusy(false);
    }
  }

  async function clearCredential(providerId: string) {
    if (!window.confirm(t("models.confirmClearCred", { id: providerId }))) return;
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const info = creds?.providers?.[providerId];
      if (info?.type === "oauth") {
        const r = await apiFetch("/api/credentials/oauth/logout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: providerId }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || t("models.logoutFail"));
      } else {
        const r = await apiFetch(`/api/credentials/${encodeURIComponent(providerId)}`, {
          method: "DELETE",
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || t("models.clearFail"));
      }
      setStatusMsg(t("models.cleared", { id: providerId }));
      await refresh();
      onChanged?.();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : t("models.clearFail"));
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
      const r = await apiFetch("/api/credentials/oauth/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: providerId, auth_type: "oauth" }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || t("models.oauthStartFail"));
      setLoginId(String(data.login_id));
      setLoginProvider(providerId);
      setStatusMsg(t("models.loggingIn", { id: providerId }));
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : t("models.oauthFail"));
    } finally {
      setBusy(false);
    }
  }

  async function submitPromptReply(value = promptValue) {
    if (!loginId || !pendingPrompt?.prompt_id) return;
    setBusy(true);
    try {
      const r = await apiFetch("/api/credentials/oauth/reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          login_id: loginId,
          prompt_id: pendingPrompt.prompt_id,
          value,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || t("models.submitFail"));
      setPromptValue("");
      setPendingPrompt(null);
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : t("models.submitFail"));
    } finally {
      setBusy(false);
    }
  }

  async function saveBaseUrl(providerId: string) {
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await apiFetch("/api/credentials/base-url", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: providerId,
          base_url: (draftBaseUrls[providerId] || "").trim(),
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || t("models.saveFail"));
      setStatusMsg(
        data.base_url
          ? t("models.baseUrlSaved", { id: providerId })
          : t("models.baseUrlCleared", { id: providerId }),
      );
      await refresh();
      onChanged?.();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : t("models.saveFail"));
    } finally {
      setBusy(false);
    }
  }

  async function deleteCustomEndpoint(item: CustomEndpoint) {
    const key = endpointKey(item);
    const label = item.display_name || item.model_id || item.profile_id;
    if (pendingDelete !== key) {
      setPendingDelete(key);
      return;
    }
    setPendingDelete(null);
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await apiFetch("/api/models/custom-endpoint", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: item.profile_id,
          provider: item.provider,
          model_id: item.model_id,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || t("models.deleteFail"));
      if (Array.isArray(data.endpoints)) setCustomEndpoints(data.endpoints);
      if (editingKey === endpointKey(item)) {
        setEditingKey(null);
        setCustomForm(EMPTY_CUSTOM_FORM);
      }
      setStatusMsg(t("models.deleted", { label }));
      await refresh();
      onChanged?.();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : t("models.deleteFail"));
    } finally {
      setBusy(false);
    }
  }

  async function saveCustomEndpoint() {
    const profileId = customForm.profile_id.trim();
    const provider = customForm.provider.trim();
    const baseUrl = customForm.base_url.trim();
    const modelId = customForm.model_id.trim();
    if (!provider || !baseUrl || !modelId) {
      setStatusError(true);
      setStatusMsg(t("models.needProviderFields"));
      return;
    }
    setBusy(true);
    setStatusMsg("");
    setStatusError(false);
    try {
      const r = await apiFetch("/api/models/custom-endpoint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...customForm, profile_id: profileId, provider, base_url: baseUrl, model_id: modelId }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || t("models.saveFail"));
      if (Array.isArray(data.endpoints)) setCustomEndpoints(data.endpoints);
      setStatusMsg(t("models.customSaved", { id: data.profile_id || profileId || modelId }));
      setCustomForm(EMPTY_CUSTOM_FORM);
      setAddingCustom(false);
      setEditingKey(null);
      await refresh();
      onChanged?.();
    } catch (e) {
      setStatusError(true);
      setStatusMsg(e instanceof Error ? e.message : t("models.saveFail"));
    } finally {
      setBusy(false);
    }
  }

  function copyCustomEndpoint(item: CustomEndpoint) {
    setPendingDelete(null);
    setEditingKey(null);
    setCustomForm({
      ...EMPTY_CUSTOM_FORM,
      provider: item.provider,
      base_url: item.base_url,
      api_type: item.api_type || "openai-completions",
    });
    setAddingCustom(true);
    setStatusError(false);
    setStatusMsg(
      t("models.copied", { provider: item.provider }),
    );
  }

  function renderCustomForm(onCancel: () => void) {
    const editing = Boolean(customForm.previous_provider || customForm.previous_profile_id);
    return (
      <>
        <div className="custom-grid">
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
            {t("models.apiType")}
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
            {t("models.displayName")}
            <input
              value={customForm.display_name}
              placeholder={t("models.localOllama")}
              onChange={(e) => setCustomForm((p) => ({ ...p, display_name: e.target.value }))}
            />
          </label>
          <label>
            {t("models.apiKeyLocal")}
            <input
              value={customForm.api_key}
              placeholder={editing ? t("models.keepKey") : t("models.writeLocal")}
              onChange={(e) => setCustomForm((p) => ({ ...p, api_key: e.target.value }))}
            />
          </label>
        </div>
        <div className="row">
          <button type="button" className="primary" disabled={busy} onClick={() => void saveCustomEndpoint()}>
            {t("models.saveEndpoint")}
          </button>
          <button type="button" disabled={busy} onClick={onCancel}>
            {t("models.cancel")}
          </button>
        </div>
      </>
    );
  }

  return (
    <div className="settings-section">
      <p className="settings-help">
        {t("models.sectionHelp")}{" "}
        <span className="mono">.local/credentials/pi-auth.json</span>{t("models.notInGit")}
      </p>

        <section className="settings-card">
          <h3>Providers</h3>
          {(loginId || authUrl || pendingPrompt) && (
            <div className="oauth-panel">
              <p className="settings-meta">
                {t("models.oauthInProgress", { suffix: loginProvider ? t("models.colonProvider", { id: loginProvider }) : "" })}
              </p>
              {authUrl ? (
                <p className="settings-help">
                  {t("models.openAuth")}{" "}
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
                            : t("models.followPrompt"))
                        }
                        style={{ flex: "1 1 240px" }}
                      />
                      <button
                        type="button"
                        className="primary"
                        disabled={busy}
                        onClick={() => void submitPromptReply()}
                      >
                        {t("models.submit")}
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
                      {info?.set ? (info.type === "oauth" ? "OAuth" : t("common.connected")) : t("models.notConfigured")}
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
                            {t("models.clear")}
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
                          {t("models.saveKey")}
                        </button>
                        {item.supports_oauth ? (
                          <button
                            type="button"
                            disabled={busy || Boolean(loginId)}
                            onClick={() => startOAuth(item.id)}
                          >
                            {item.oauth_label || t("models.authLogin")}
                          </button>
                        ) : null}
                        {item.keys_url ? (
                          <a href={item.keys_url} target="_blank" rel="noreferrer">
                            {t("models.getKey")}
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
                                  ? t("models.emptyDefaultUrl", { url: item.default_base_url })
                                  : t("models.emptyPiDefault")
                              }
                              style={{ flex: "1 1 260px" }}
                            />
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => saveBaseUrl(item.id)}
                            >
                              {t("models.saveUrl")}
                            </button>
                          </div>
                          <p className="settings-meta" style={{ marginTop: 6 }}>
                            {override?.base_url
                              ? t("models.currentOverride", { url: override.base_url })
                              : t("models.currentPiDefault", { suffix: item.default_base_url ? t("models.parenUrl", { url: item.default_base_url }) : "" })}
                            {item.base_url_hint ? ` · ${item.base_url_hint}` : ""}
                          </p>
                        </div>
                      ) : null}
                      {item.id === "openai" ? (
                        <p className="settings-meta" style={{ marginTop: 10 }}>
                          {t("models.oauthKeyOverride")}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </section>

        <section className="settings-card">
          <h3>{t("models.customTitle")}</h3>
          <p className="settings-help">
            {t("models.customHelp")}
          </p>
          {customEndpoints.length ? (
            <ul className="custom-saved">
              {customEndpoints.map((item) => {
                const key = endpointKey(item);
                const editing = editingKey === key;
                const label = item.display_name || item.model_id || item.profile_id;
                return (
                  <li key={key}>
                    <div className="custom-saved-head">
                      <div className="custom-saved-copy">
                        <div className="custom-saved-title">
                          <strong>{item.display_name || item.model_id}</strong>
                          <span className="badge badge-ok">{t("models.savedBadge")}</span>
                        </div>
                        {editing ? null : (
                          <>
                            <p className="settings-meta">
                              {item.profile_id ? `${item.profile_id} · ` : ""}
                              {item.provider}/{item.model_id}
                              {item.api_type ? ` · ${item.api_type}` : ""}
                            </p>
                            {item.base_url ? <p className="settings-meta">{item.base_url}</p> : null}
                          </>
                        )}
                      </div>
                      <span className="custom-saved-actions">
                        <button
                          type="button"
                          className="danger"
                          disabled={busy}
                          aria-label={pendingDelete === key ? t("models.confirmDeleteLabel", { label }) : t("models.deleteLabel", { label })}
                          onClick={() => void deleteCustomEndpoint(item)}
                        >
                          <Trash2 size={14} strokeWidth={1.75} aria-hidden="true" />
                          {pendingDelete === key ? t("common.confirmDelete") : t("common.delete")}
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => copyCustomEndpoint(item)}
                        >
                          <Copy size={14} strokeWidth={1.75} aria-hidden="true" />
                          {t("models.copy")}
                        </button>
                        <button
                          type="button"
                          disabled={busy || editing}
                          onClick={() => {
                            setPendingDelete(null);
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
                          <Pencil size={14} strokeWidth={1.75} aria-hidden="true" />
                          {t("models.edit")}
                        </button>
                      </span>
                    </div>
                    {editing
                      ? renderCustomForm(() => {
                          setEditingKey(null);
                          setCustomForm(EMPTY_CUSTOM_FORM);
                        })
                      : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="settings-help">{t("models.noCustom")}</p>
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
              {t("models.addCustom")}
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
