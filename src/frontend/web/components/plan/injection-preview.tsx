"use client";

// Prompt preview modal: same <dialog className="settings-dialog"> frame and CSS as the settings modal.
// Shows one agent's exact round-1 system prompt / user message from /api/v5/preview (read-only), scrolling inside.
import { useEffect, useRef, useState } from "react";
import { label } from "../../lib/labels";

export type PreviewAgent = { role: string; system: string; user: string };
export type PreviewData = {
  nodes: { id: string; title: string; agents: PreviewAgent[] }[];
  plan_present?: boolean;
  plan_source?: string;
};

const PARTS = [
  { id: "system", label: "系统提示" },
  { id: "user", label: "用户消息" },
] as const;

export function PromptModal({ node, agent, onClose }: { node: { id: string; title: string } | null; agent: PreviewAgent | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [part, setPart] = useState<"system" | "user">("system");
  const open = Boolean(node && agent);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
    if (open) setPart("system");
  }, [open]);
  return (
    <dialog ref={ref} className="settings-dialog" aria-labelledby="prompt-modal-title" data-testid="prompt-modal"
      onClose={onClose}
      onClick={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (r && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) onClose();
      }}>
      <div className="settings-frame">
        <nav className="settings-nav" aria-label="组合注入">
          <p id="prompt-modal-title" className="settings-nav-label">组合注入</p>
          {PARTS.map((p) => (
            <button key={p.id} type="button" aria-current={part === p.id ? "page" : undefined} onClick={() => setPart(p.id)}>
              {p.label}
            </button>
          ))}
        </nav>
        <div className="settings-main">
          <header className="settings-main-head">
            <div>
              <p className="settings-crumb">组合注入 / {node?.title || node?.id} / {agent ? label(agent.role) : ""}</p>
              <h2>{PARTS.find((p) => p.id === part)?.label}</h2>
            </div>
            <button type="button" data-testid="prompt-modal-close" onClick={onClose}>
              关闭
            </button>
          </header>
          <div className="settings-body">
            {agent ? (
              <pre className="harness-source prompt-modal-source">
                <code>{part === "system" ? agent.system : agent.user}</code>
              </pre>
            ) : null}
          </div>
        </div>
      </div>
    </dialog>
  );
}
