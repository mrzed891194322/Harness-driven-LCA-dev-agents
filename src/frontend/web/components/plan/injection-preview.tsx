"use client";

// Prompt preview in 599ed0a InjectionBoard style (injection-board / injection-tree / injection-detail CSS),
// fed by /api/v5/preview: each agent's exact round-1 system prompt and user message (read-only).
import { useState } from "react";
import { label } from "../../lib/labels";

export type PreviewData = {
  nodes: { id: string; title: string; agents: { role: string; system: string; user: string }[] }[];
  plan_source?: string;
};

export function InjectionPreview({ preview }: { preview: PreviewData }) {
  const [selected, setSelected] = useState("");
  const node = preview.nodes.find((n) => n.agents.some((a) => `${n.id}.${a.role}` === selected));
  const agent = node?.agents.find((a) => `${node.id}.${a.role}` === selected);
  return (
    <div className="injection-board" data-testid="preview-injection">
      <div className="injection-split">
        <nav className="injection-tree" aria-label="阶段与分工">
          {preview.nodes.map((n) => (
            <div key={n.id} className="injection-stage">
              <p className="injection-stage-title">{n.title || n.id}</p>
              <ul>
                {n.agents.map((a) => {
                  const key = `${n.id}.${a.role}`;
                  return (
                    <li key={key}>
                      <button type="button" data-testid={`preview-agent-${key}`}
                        aria-current={selected === key ? "true" : undefined} onClick={() => setSelected(key)}>
                        {key}
                        <span className="injection-role">{label(a.role)}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
        <div className="injection-detail">
          {!agent || !node ? (
            <p className="harness-status">选择左侧分工查看组合注入（只读）。</p>
          ) : (
            <>
              <header className="injection-detail-head">
                <h3>{`${node.id}.${agent.role}`}</h3>
              </header>
              <section className="injection-group">
                <h3>系统提示</h3>
                <pre className="harness-source"><code>{agent.system}</code></pre>
              </section>
              <section className="injection-group">
                <h3>用户消息</h3>
                <pre className="harness-source"><code>{agent.user}</code></pre>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
