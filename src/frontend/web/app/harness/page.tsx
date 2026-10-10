"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  HarnessShell,
  harnessHref,
  type HarnessCatalog,
} from "../../components/harness/harness-shell";
import { apiFetch } from "../../lib/api";

export default function HarnessIndexPage() {
  const router = useRouter();
  const [catalog, setCatalog] = useState<HarnessCatalog | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await apiFetch("/api/harness/catalog");
        const data = (await response.json()) as HarnessCatalog & { detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法加载 Harness 目录");
        if (cancelled) return;
        setCatalog(data);
        const first = data.sections[0]?.groups[0]?.entries[0]?.path;
        if (first) router.replace(harnessHref(first));
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "无法加载 Harness 目录");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (error) {
    return (
      <HarnessShell catalog={catalog} selected="" error={error}>
        <p className="harness-status">{error}</p>
      </HarnessShell>
    );
  }

  return (
    <HarnessShell catalog={catalog} selected="">
      <p className="harness-status">正在打开 Harness…</p>
    </HarnessShell>
  );
}
