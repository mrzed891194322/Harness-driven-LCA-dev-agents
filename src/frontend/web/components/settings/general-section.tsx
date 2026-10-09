"use client";

import { useEffect, useState } from "react";

type PortField = {
  id: string;
  label: string;
  hint: string;
  envKey: string;
};

const PORT_FIELDS: PortField[] = [
  {
    id: "openlca",
    label: "openLCA IPC",
    hint: "与 openLCA 偏好设置中的 IPC Server 端口一致。",
    envKey: "OPENLCA_IPC_PORT",
  },
];

export function GeneralSection({ onChanged }: { onChanged?: () => void }) {
  const [host, setHost] = useState("127.0.0.1");
  const [ports, setPorts] = useState<Record<string, string>>({ openlca: "8080" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [tone, setTone] = useState<"ok" | "warn" | "error">("ok");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/lca/openlca")
      .then(async (response) => {
        const data = (await response.json()) as { host?: string; port?: number; detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法读取端口");
        if (cancelled) return;
        if (data.host) setHost(data.host);
        if (data.port != null) setPorts((prev) => ({ ...prev, openlca: String(data.port) }));
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setTone("error");
        setMessage(error instanceof Error ? error.message : "无法读取端口");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function saveOpenLca() {
    const port = Number(ports.openlca);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      setTone("error");
      setMessage("端口须为 1–65535 的整数");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/lca/openlca", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ port }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "保存端口失败");
      const tool = data.tool as { ok?: boolean; message?: string; port?: number; host?: string } | undefined;
      if (tool?.port != null) setPorts((prev) => ({ ...prev, openlca: String(tool.port) }));
      if (tool?.host) setHost(tool.host);
      setTone(tool?.ok ? "ok" : "warn");
      setMessage(
        tool
          ? `已保存端口 ${tool.port}。${tool.message}`
          : `已保存端口 ${port}`,
      );
      onChanged?.();
    } catch (error: unknown) {
      setTone("error");
      setMessage(error instanceof Error ? error.message : "保存端口失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings-section">
      <p className="settings-help">连接端口写入项目根目录的 .env，保存后立即重新检查。</p>
      {PORT_FIELDS.map((field) => (
        <section key={field.id} className="settings-card">
          <h3>{field.label}</h3>
          <p className="settings-help">{field.hint}</p>
          <div className="row">
            <label className="inline-field">
              端口
              <input
                type="number"
                min={1}
                max={65535}
                value={ports[field.id] ?? ""}
                onChange={(event) =>
                  setPorts((prev) => ({ ...prev, [field.id]: event.target.value }))
                }
              />
            </label>
            <span className="settings-meta">
              主机 {host} · <span className="mono">{field.envKey}</span>
            </span>
            <button type="button" className="primary" disabled={busy} onClick={() => void saveOpenLca()}>
              {busy ? "检查中…" : "保存并检查"}
            </button>
          </div>
        </section>
      ))}
      {message ? (
        <div className={`status-banner${tone === "ok" ? "" : ` ${tone}`}`} role="status">
          {message}
        </div>
      ) : null}
    </div>
  );
}
