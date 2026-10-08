"use client";

import { useEffect, useMemo, useState } from "react";

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

const FALLBACK_PROVIDERS = ["anthropic", "openai", "google", "openrouter"];

export default function SettingsPage() {
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [profile, setProfile] = useState("default");
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const r = await fetch("/api/diagnostics/environment");
    const data = (await r.json()) as Diagnostics;
    setDiag(data);
    const selected = data.selected_profile || "default";
    setProfile(selected);
    const selectedProfile = data.profiles?.[selected];
    if (selectedProfile?.provider) {
      setProvider(selectedProfile.provider);
    }
  }

  useEffect(() => {
    refresh().catch(() => setDiag(null));
  }, []);

  const profiles = diag?.profiles ?? {
    default: { provider: "anthropic", model_id: "", display_name: "项目默认" },
  };

  const providerOptions = useMemo(() => {
    const fromProfiles = Object.values(profiles)
      .map((p) => p.provider)
      .filter(Boolean);
    return Array.from(new Set([...fromProfiles, ...FALLBACK_PROVIDERS]));
  }, [profiles]);

  const currentProfile = profiles[profile];
  const providerConfigured = Boolean(diag?.credentials?.[provider]);

  async function saveModel() {
    setBusy(true);
    setStatusMsg("");
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
      if (currentProfile?.provider) {
        setProvider(currentProfile.provider);
      }
      setStatusMsg(`已保存默认模型档案：${profile}`);
      await refresh();
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveCredential() {
    if (!apiKey.trim()) {
      setStatusMsg("请填写 API Key");
      return;
    }
    setBusy(true);
    setStatusMsg("");
    try {
      const r = await fetch("/api/credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      if (!r.ok) {
        throw new Error("凭证保存失败");
      }
      setApiKey("");
      setStatusMsg(`已保存 ${provider} API Key（不回显）`);
      await refresh();
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "凭证保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    setBusy(true);
    setStatusMsg("");
    try {
      const r = await fetch("/api/models/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: profile, provider }),
      });
      const data = await r.json();
      setStatusMsg(
        data.ok
          ? `连接成功：${data.provider}/${data.model_id}${data.mode ? ` (${data.mode})` : ""}`
          : `连接失败：${data.message || "未知错误"}`,
      );
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "测试失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 720, lineHeight: 1.5 }}>
      <h2>设置与初始化</h2>
      <p style={{ color: "#444" }}>
        Worker 固定为 Pi SDK runtime。选择模型档案，并为对应 Provider 填入自有 API Key（BYOK）。
      </p>

      {diag ? (
        <ul>
          <li>
            Node / pi-runtime: {diag.pi_agents.ok ? "✓" : "✗"} {diag.pi_agents.message}
          </li>
          <li>
            Python 环境: {diag.python_agent.ok ? "✓" : "✗"} {diag.python_agent.message}
          </li>
          <li>
            openLCA: {diag.openlca.ok ? "✓" : "✗"} {diag.openlca.message}
          </li>
        </ul>
      ) : (
        <p>加载诊断…</p>
      )}

      <section style={{ marginTop: 24 }}>
        <h3>模型档案（PI_MODEL）</h3>
        <select
          value={profile}
          onChange={(e) => {
            const id = e.target.value;
            setProfile(id);
            const p = profiles[id];
            if (p?.provider) setProvider(p.provider);
          }}
        >
          {Object.entries(profiles).map(([id, p]) => (
            <option key={id} value={id}>
              {p.display_name ?? id} ({p.provider}/{p.model_id})
            </option>
          ))}
        </select>
        <button type="button" onClick={saveModel} disabled={busy} style={{ marginLeft: 8 }}>
          保存默认模型
        </button>
        {currentProfile ? (
          <p style={{ marginTop: 8, color: "#555" }}>
            当前档案：{currentProfile.provider}/{currentProfile.model_id}
            {currentProfile.base_url ? ` @ ${currentProfile.base_url}` : ""}
          </p>
        ) : null}
      </section>

      <section style={{ marginTop: 24 }}>
        <h3>凭证（BYOK，不回显）</h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providerOptions.map((id) => (
              <option key={id} value={id}>
                {id}
                {diag?.credentials?.[id] ? "（已配置）" : ""}
              </option>
            ))}
          </select>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="API key"
            autoComplete="off"
            style={{ minWidth: 220 }}
          />
          <button type="button" onClick={saveCredential} disabled={busy}>
            保存密钥
          </button>
          <button type="button" onClick={testConnection} disabled={busy}>
            测试连接
          </button>
        </div>
        <p style={{ marginTop: 8, color: "#555" }}>
          {provider}：{providerConfigured ? "已配置" : "未配置"}
        </p>
      </section>

      {statusMsg ? (
        <p style={{ marginTop: 16 }} role="status">
          {statusMsg}
        </p>
      ) : null}

      <button type="button" onClick={() => refresh()} disabled={busy} style={{ marginTop: 16 }}>
        重新检查环境
      </button>
    </div>
  );
}
