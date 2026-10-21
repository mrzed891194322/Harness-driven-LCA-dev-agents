"use client";

// Q8: read-only v5 YAML viewer laid out like the original Harness page (master 599ed0a harness-shell):
// left settings/tutorial nav with section and group labels, crumb + title header with close button, doc body.
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw, X } from "lucide-react";
import { apiFetch } from "../../lib/api";
import { fieldRows, rawLines, type HarnessFile, type HarnessSection } from "../../lib/harness-view";

export default function HarnessPage() {
  const router = useRouter();
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
    document.documentElement.classList.add("status-fit");
    return () => document.documentElement.classList.remove("status-fit");
  }, []);

  useEffect(() => {
    document.querySelector(".tutorial-body")?.scrollTo(0, 0);
  }, [selected, section]);

  const current = sections.find((s) => s.id === section);
  const files = useMemo(() => current?.files || [], [current]);
  const file: HarnessFile | undefined = files.find((f) => f.path === selected) || files[0];
  const crumb = ["Harness", current?.title, file?.group].filter(Boolean).join(" / ");

  return (
    <section className="tutorial-panel settings-card" data-testid="harness-viewer">
      <div className="tutorial-frame">
        <nav className="settings-nav harness-nav tutorial-nav" aria-label="Harness">
          <p className="settings-nav-label">Harness（只读）</p>
          {sections.map((s) => {
            const groups = [...new Set(s.files.map((f) => f.group))];
            return (
              <div key={s.id}>
                <button
                  type="button"
                  className="harness-nav-section"
                  data-testid={`harness-tab-${s.id}`}
                  aria-selected={section === s.id}
                  onClick={() => {
                    setSection(s.id);
                    setSelected("");
                  }}
                  style={{ background: "none", border: 0, padding: 0, cursor: "pointer", textAlign: "left" }}
                >
                  {s.title}
                  {s.files.some((f) => f.error) ? " ⚠" : ""}
                </button>
                {groups.map((g) => (
                  <div key={g}>
                    {groups.length > 1 ? <p className="harness-nav-group">{g}</p> : null}
                    {s.files
                      .filter((f) => f.group === g)
                      .map((f) => {
                        const active = section === s.id && file?.path === f.path;
                        return (
                          <a
                            key={f.path}
                            href="#"
                            data-testid={`harness-file-${f.path}`}
                            aria-current={active ? "page" : undefined}
                            data-active={active ? "true" : undefined}
                            onClick={(e) => {
                              e.preventDefault();
                              setSection(s.id);
                              setSelected(f.path);
                            }}
                          >
                            {f.name}
                            {f.error ? " ⚠" : ""}
                          </a>
                        );
                      })}
                  </div>
                ))}
              </div>
            );
          })}
          {!sections.length && !loadError ? <p className="harness-status">加载目录…</p> : null}
        </nav>
        <div className="settings-main tutorial-main">
          <header className="settings-main-head tutorial-main-head">
            <div>
              <p className="settings-crumb">
                {crumb}
                {errors ? (
                  <span className="badge badge-fail" data-testid="harness-error-count"> {errors} 个文件加载失败</span>
                ) : null}
              </p>
              <h2>{file?.name || "Harness"}</h2>
              {file ? <p className="harness-path mono">{file.path}</p> : null}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button type="button" onClick={() => void load()} disabled={busy} title="刷新">
                <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="tutorial-close"
                aria-label="关闭 Harness"
                title="返回上一页"
                onClick={() => (window.history.length > 1 ? router.back() : router.push("/"))}
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>
          </header>
          <div className="settings-body tutorial-body">
            {loadError ? <p className="status-banner error">{loadError}</p> : null}
            {file ? (
              <article className="harness-doc">
                {file.error ? (
                  <p className="status-banner error" data-testid="harness-file-error">
                    {file.error.line ? `${file.path}:${file.error.line} — ` : ""}
                    {file.error.message}
                  </p>
                ) : null}
                {file.fields ? (
                  <div className="harness-table-wrap">
                    <table data-testid="harness-fields">
                      <tbody>
                        {fieldRows(file.fields).map(([key, text, multi]) => (
                          <tr key={key}>
                            <th>{key}</th>
                            <td>{multi ? <pre className="harness-source"><code>{text}</code></pre> : text}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                <h3>原始 YAML</h3>
                <pre className="harness-source" data-testid="harness-raw">
                  <code>
                    {rawLines(file.raw, file.error?.line).map((l) => (
                      <span key={l.n} className={l.bad ? "status-banner error" : undefined} style={{ display: "block" }}>
                        {String(l.n).padStart(3, " ")}  {l.text}
                      </span>
                    ))}
                  </code>
                </pre>
              </article>
            ) : sections.length ? (
              <p className="settings-help">这一类还没有文件。</p>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
