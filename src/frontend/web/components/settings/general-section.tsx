"use client";

import { useState } from "react";

type PortField = {
  id: "web" | "api";
  label: string;
  envKey: string;
};

const PORT_FIELDS: PortField[] = [
  { id: "web", label: "前端", envKey: "GUI_WEB_PORT" },
  { id: "api", label: "后端", envKey: "GUI_API_PORT" },
];

const CACHE_OPTIONS = [
  { id: "user-input", label: "用户输入" },
  { id: "knowledge", label: "知识库" },
  { id: "workspace", label: "工作区" },
  { id: "olca", label: "openLCA产物" },
] as const;

function validPort(value: string) {
  const port = Number(value);
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

export function GeneralSection(_props: { onChanged?: () => void }) {
  const [host] = useState("127.0.0.1");
  const [ports, setPorts] = useState<Record<PortField["id"], string>>({
    web: "3000",
    api: "8800",
  });
  const [message, setMessage] = useState("");
  const [tone, setTone] = useState<"ok" | "error">("ok");
  const [cacheTargets, setCacheTargets] = useState<Record<string, boolean>>({});
  const [agentLanguage, setAgentLanguage] = useState("中文");
  const [languageMessage, setLanguageMessage] = useState("");
  const [languageTone, setLanguageTone] = useState<"ok" | "error">("ok");

  function savePorts() {
    const invalid = PORT_FIELDS.find((field) => !validPort(ports[field.id]));
    if (invalid) {
      setTone("error");
      setMessage(`${invalid.label}端口须为 1–65535 的整数`);
      return;
    }
    if (ports.web === ports.api) {
      setTone("error");
      setMessage("前端与后端端口不能相同");
      return;
    }
    setTone("ok");
    setMessage("端口已记录，重启后生效。");
  }

  function saveLanguage() {
    const value = agentLanguage.trim();
    if (!value) {
      setLanguageTone("error");
      setLanguageMessage("请填写语言");
      return;
    }
    setAgentLanguage(value);
    setLanguageTone("ok");
    setLanguageMessage("语言已记录。");
  }

  return (
    <div className="settings-section">
      <section className="settings-card">
        <h3>端口设置</h3>
        <p className="settings-help">保存后重启生效。</p>
        {PORT_FIELDS.map((field) => (
          <div key={field.id} className="row">
            <label className="inline-field">
              {field.label}
              <input
                type="number"
                min={1}
                max={65535}
                aria-label={`${field.label}端口`}
                value={ports[field.id]}
                onChange={(event) => {
                  setMessage("");
                  setPorts((prev) => ({ ...prev, [field.id]: event.target.value }));
                }}
              />
            </label>
            <span className="settings-meta">
              主机 {host} · <span className="mono">{field.envKey}</span>
            </span>
          </div>
        ))}
        <div className="row">
          <button type="button" className="primary" onClick={savePorts}>
            保存
          </button>
        </div>
        {message ? (
          <div className={`status-banner${tone === "ok" ? "" : ` ${tone}`}`} role="status">
            {message}
          </div>
        ) : null}
      </section>

      <section className="settings-card">
        <h3 className="settings-card-title">
          清理缓存
          <span className="badge badge-warn">开发中，功能未完善</span>
        </h3>
        <ul className="settings-checks">
          {CACHE_OPTIONS.map((option) => (
            <li key={option.id}>
              <label className="settings-check">
                <input
                  type="checkbox"
                  checked={Boolean(cacheTargets[option.id])}
                  onChange={(event) =>
                    setCacheTargets((prev) => ({ ...prev, [option.id]: event.target.checked }))
                  }
                />
                <span>{option.label}</span>
              </label>
            </li>
          ))}
        </ul>
        <div className="row">
          <button type="button">清除</button>
        </div>
      </section>

      <section className="settings-card">
        <h3 className="settings-card-title">
          Agent 语言
          <span className="badge badge-warn">开发中，功能未完善</span>
        </h3>
        <p className="settings-help">agent将会倾向以这种语言进行输出，但不影响GUI显示语言</p>
        <div className="row">
          <label className="inline-field">
            语言
            <input
              type="text"
              className="agent-language"
              aria-label="Agent 语言"
              value={agentLanguage}
              placeholder="例如：中文"
              onChange={(event) => {
                setLanguageMessage("");
                setAgentLanguage(event.target.value);
              }}
            />
          </label>
        </div>
        <div className="row">
          <button type="button" className="primary" onClick={saveLanguage}>
            保存
          </button>
        </div>
        {languageMessage ? (
          <div className={`status-banner${languageTone === "ok" ? "" : ` ${languageTone}`}`} role="status">
            {languageMessage}
          </div>
        ) : null}
      </section>
    </div>
  );
}
