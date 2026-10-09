"use client";

import { useEffect, useState } from "react";
import { BACKEND_DOWN_MESSAGE, backendReachable } from "../lib/api";

/** Banner shown on every page while the backend does not answer /api/health. */
export function BackendStatus() {
  const [down, setDown] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function check() {
      const ok = await backendReachable();
      if (cancelled) return;
      setDown(!ok);
      timer = setTimeout(() => void check(), ok ? 10_000 : 3_000);
    }
    void check();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (!down) return null;
  return (
    <div className="backend-status-banner" role="alert">
      {BACKEND_DOWN_MESSAGE}
    </div>
  );
}
