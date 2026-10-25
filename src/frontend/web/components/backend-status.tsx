"use client";

import { useEffect, useState } from "react";
import { backendReachable } from "../lib/api";
import { useLocale } from "../lib/i18n/locale-context";

/** Banner shown on every page while the backend does not answer /api/health. */
export function BackendStatus() {
  const [down, setDown] = useState(false);
  const { t } = useLocale();

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
      {t("api.backendDown")}
    </div>
  );
}
