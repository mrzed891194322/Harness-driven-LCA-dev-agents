"use client";

import { useState } from "react";
import { useLocale } from "../../lib/i18n/locale-context";

type PortId = "web" | "api";

const PORT_FIELDS: { id: PortId; envKey: string }[] = [
  { id: "web", envKey: "GUI_WEB_PORT" },
  { id: "api", envKey: "GUI_API_PORT" },
];

const CACHE_OPTIONS = [
  { id: "user-input", key: "general.cacheUserInput" },
  { id: "knowledge", key: "general.cacheKnowledge" },
  { id: "workspace", key: "general.cacheWorkspace" },
  { id: "olca", key: "general.cacheOlca" },
] as const;

function validPort(value: string) {
  const port = Number(value);
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

export function GeneralSection(_props: { onChanged?: () => void }) {
  const { t } = useLocale();
  const [host] = useState("127.0.0.1");
  const [ports, setPorts] = useState<Record<PortId, string>>({
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
      setMessage(`${t("general." + invalid.id)}: ${t("general.portInvalid")}`);
      return;
    }
    if (ports.web === ports.api) {
      setTone("error");
      setMessage(t("general.portSame"));
      return;
    }
    setTone("ok");
    setMessage(t("general.portSaved"));
  }

  function saveLanguage() {
    const value = agentLanguage.trim();
    if (!value) {
      setLanguageTone("error");
      setLanguageMessage(t("general.agentLangEmpty"));
      return;
    }
    setAgentLanguage(value);
    setLanguageTone("ok");
    setLanguageMessage(t("general.agentLangSaved"));
  }

  return (
    <div className="settings-section">
      <section className="settings-card">
        <h3>{t("general.ports")}</h3>
        <p className="settings-help">{t("general.portsHelp")}</p>
        {PORT_FIELDS.map((field) => (
          <div key={field.id} className="row">
            <label className="inline-field">
              {t(field.id === "web" ? "general.web" : "general.api")}
              <input
                type="number"
                min={1}
                max={65535}
                aria-label={t(field.id === "web" ? "general.web" : "general.api")}
                value={ports[field.id]}
                onChange={(event) => {
                  setMessage("");
                  setPorts((prev) => ({ ...prev, [field.id]: event.target.value }));
                }}
              />
            </label>
            <span className="settings-meta">
              {t("general.host")} {host} · <span className="mono">{field.envKey}</span>
            </span>
          </div>
        ))}
        <div className="row">
          <button type="button" className="primary" onClick={savePorts}>
            {t("general.save")}
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
          {t("general.cache")}
          <span className="badge badge-warn">{t("general.cacheDev")}</span>
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
                <span>{t(option.key)}</span>
              </label>
            </li>
          ))}
        </ul>
        <div className="row">
          <button type="button">{t("general.clear")}</button>
        </div>
      </section>

      <section className="settings-card">
        <h3 className="settings-card-title">
          {t("general.agentLang")}
          <span className="badge badge-warn">{t("general.cacheDev")}</span>
        </h3>
        <p className="settings-help">{t("general.agentLangHelp")}</p>
        <div className="row">
          <label className="inline-field">
            {t("general.agentLangLabel")}
            <input
              type="text"
              className="agent-language"
              aria-label={t("general.agentLang")}
              value={agentLanguage}
              placeholder={t("general.agentLangPh")}
              onChange={(event) => {
                setLanguageMessage("");
                setAgentLanguage(event.target.value);
              }}
            />
          </label>
        </div>
        <div className="row">
          <button type="button" className="primary" onClick={saveLanguage}>
            {t("general.save")}
          </button>
        </div>
        {languageMessage ? (
          <div
            className={`status-banner${languageTone === "ok" ? "" : ` ${languageTone}`}`}
            role="status"
          >
            {languageMessage}
          </div>
        ) : null}
      </section>
    </div>
  );
}
