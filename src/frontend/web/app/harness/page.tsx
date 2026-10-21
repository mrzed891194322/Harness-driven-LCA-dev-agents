"use client";

import { useEffect, useMemo, useState } from "react";
import { FileCode2, RefreshCw } from "lucide-react";
import { apiFetch } from "../../lib/api";
import { fieldRows, rawLines, type HarnessFile, type HarnessSection } from "../../lib/harness-view";

export default function HarnessPage() {
  const [sections, setSections] = useState<HarnessSection[]>([]);
  const [errors, setErrors] = useState(0);
  const [section, setSection] = useState("rules");
  const [selected, setSelected] = useState("");
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      const response = await apiFetch("/api/v5/harness", { cache: "no-store" });
      const body = (await response.json()) as { sections: HarnessSection[]; errors: number; detail?: string };
      if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
      setSections(body.sections);
      setErrors(body.errors);
      setLoadError("");
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const files = useMemo(() => sections.find((s) => s.id === section)?.files || [], [sections, section]);
  const file: HarnessFile | undefined = files.find((f) => f.path === selected) || files[0];
  const groups = useMemo(() => [...new Set(files.map((f) => f.group))], [files]);

  return (
    <div className="plan-board">
      <section className="settings-card plan-card results-card" data-testid="harness-viewer">
        <div className="section-head plan-head">
          <div className="plan-intro">
            <h2>
              <FileCode2 className="plan-title-icon" size={20} strokeWidth={1.75} aria-hidden="true" />
              Harness（只读）
            </h2>
            <p className="settings-meta">
              harness/ 下的 v5 YAML：规则、角色、规格、工作流。
              {errors ? (
                <span className="badge badge-fail" data-testid="harness-error-count"> {errors} 个文件加载失败</span>
              ) : sections.length ? (
                <span className="badge badge-ok"> 全部加载成功</span>
              ) : null}
            </p>
          </div>
          <div className="run-meta">
            <button type="button" onClick={() => void load()} disabled={busy}>
              <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
              {busy ? "刷新中…" : "刷新"}
            </button>
          </div>
        </div>
        {loadError ? <p className="status-banner error">{loadError}</p> : null}
        <div className="results-columns">
          <div className="results-side">
            <div className="results-kind-tabs" role="tablist" aria-label="Harness 分类">
              {sections.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  role="tab"
                  data-testid={`harness-tab-${s.id}`}
                  aria-selected={section === s.id}
                  className={section === s.id ? "is-active" : ""}
                  onClick={() => {
                    setSection(s.id);
                    setSelected("");
                  }}
                >
                  {s.title}
                  {s.files.some((f) => f.error) ? " ⚠" : ""}
                </button>
              ))}
            </div>
            <nav className="results-pane results-nav" aria-label="文件">
              {groups.map((g) => (
                <section key={g}>
                  {groups.length > 1 ? <h3>{g}</h3> : null}
                  <ul>
                    {files
                      .filter((f) => f.group === g)
                      .map((f) => (
                        <li key={f.path}>
                          <button
                            type="button"
                            data-testid={`harness-file-${f.path}`}
                            aria-current={file?.path === f.path ? "page" : undefined}
                            onClick={() => setSelected(f.path)}
                          >
                            <strong>{f.name}</strong>
                            <span>{f.error ? <span className="badge badge-fail">错误</span> : f.path}</span>
                          </button>
                        </li>
                      ))}
                  </ul>
                </section>
              ))}
              {!files.length ? <p className="settings-help">这一类还没有文件。</p> : null}
            </nav>
          </div>
          <section className="results-pane results-view" aria-label="文件内容">
            {file ? (
              <>
                <header className="results-view-head">
                  <strong className="results-path">{file.path}</strong>
                </header>
                <div className="results-view-body">
                  {file.error ? (
                    <p className="status-banner error" data-testid="harness-file-error">
                      {file.error.line ? `${file.path}:${file.error.line} — ` : ""}
                      {file.error.message}
                    </p>
                  ) : null}
                  {file.fields ? (
                    <div className="agent-table">
                      <table data-testid="harness-fields">
                        <tbody>
                          {fieldRows(file.fields).map(([key, text, multi]) => (
                            <tr key={key}>
                              <th>{key}</th>
                              <td>{multi ? <pre className="results-source"><code>{text}</code></pre> : text}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  <h3>原始 YAML</h3>
                  <pre className="results-source" data-testid="harness-raw">
                    <code>
                      {rawLines(file.raw, file.error?.line).map((l) => (
                        <span key={l.n} className={l.bad ? "status-banner error" : undefined} style={{ display: "block" }}>
                          {String(l.n).padStart(3, " ")}  {l.text}
                        </span>
                      ))}
                    </code>
                  </pre>
                </div>
              </>
            ) : (
              <p className="settings-help">选择左侧文件查看内容。</p>
            )}
          </section>
        </div>
      </section>
    </div>
  );
}
