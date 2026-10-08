"use client";

import { useEffect, useState } from "react";

type Diagnostics = {
  node: { ok: boolean; message: string };
  pi_runtime: { ok: boolean; message: string };
  python_agent: { ok: boolean; message: string };
  openlca: { ok: boolean; message: string };
  profiles: Record<string, { display_name?: string; provider: string; model_id: string }>;
};

export default function SettingsPage() {
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [profile, setProfile] = useState("default");
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    fetch("/api/diagnostics/environment")
      .then((r) => r.json())
      .then(setDiag)
      .catch(() => setDiag(null));
  }, []);

  async function saveModel() {
    await fetch("/api/models/selection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profile }),
    });
  }

  async function saveCredential() {
    if (!apiKey.trim()) return;
    await fetch("/api/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey }),
    });
    setApiKey("");
  }

  return (
    <div>
      <h2>设置与初始化</h2>
      {diag ? (
        <ul>
          <li>Node / runtime: {diag.pi_runtime.ok ? "✓" : "✗"} {diag.pi_runtime.message}</li>
          <li>Python: {diag.python_agent.ok ? "✓" : "✗"} {diag.python_agent.message}</li>
          <li>openLCA: {diag.openlca.ok ? "✓" : "✗"} {diag.openlca.message}</li>
        </ul>
      ) : (
        <p>加载诊断…</p>
      )}
      <section style={{ marginTop: 24 }}>
        <h3>模型档案</h3>
        <select value={profile} onChange={(e) => setProfile(e.target.value)}>
          {Object.entries(diag?.profiles ?? { default: { provider: "anthropic", model_id: "" } }).map(
            ([id, p]) => (
              <option key={id} value={id}>
                {p.display_name ?? id} ({p.provider}/{p.model_id})
              </option>
            ),
          )}
        </select>
        <button type="button" onClick={saveModel} style={{ marginLeft: 8 }}>保存默认模型</button>
      </section>
      <section style={{ marginTop: 24 }}>
        <h3>凭证（不回显）</h3>
        <input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="provider" />
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="API key"
          style={{ marginLeft: 8 }}
        />
        <button type="button" onClick={saveCredential} style={{ marginLeft: 8 }}>保存</button>
      </section>
    </div>
  );
}
