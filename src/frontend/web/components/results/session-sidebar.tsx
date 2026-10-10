"use client";

import type { ReactNode } from "react";
import { INJECTION_LEVEL_LABEL, INJECTION_TONE, type SessionRow } from "./run-api";

type Props = {
  sessions: SessionRow[];
  session: string;
  onSelect: (session: string) => void;
  children: ReactNode;
};

export function SessionSidebar({ sessions, session, onSelect, children }: Props) {
  return (
    <div className="results-run-detail" style={{ display: "flex", gap: 12, marginTop: 8 }}>
      <ul style={{ minWidth: 220, fontSize: 13, listStyle: "none", padding: 0, margin: 0 }}>
        {sessions.map((s) => (
          <li key={s.session}>
            <button
              type="button"
              className="link-button"
              onClick={() => onSelect(s.session)}
              style={{ fontWeight: s.session === session ? 700 : 400 }}
            >
              <span className={`badge badge-${INJECTION_TONE[s.level] || "off"}`}>
                {INJECTION_LEVEL_LABEL[s.level] || s.level}
              </span>{" "}
              {s.session}
            </button>
          </li>
        ))}
      </ul>
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    </div>
  );
}
