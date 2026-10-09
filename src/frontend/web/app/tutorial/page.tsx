"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TutorialShell, type TutorialCatalog } from "../../components/tutorial/tutorial-shell";
import { apiFetch } from "../../lib/api";

export default function TutorialIndexPage() {
  const router = useRouter();
  const [catalog, setCatalog] = useState<TutorialCatalog | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await apiFetch("/api/tutorial/catalog");
        const data = (await response.json()) as TutorialCatalog & { detail?: string };
        if (!response.ok) throw new Error(data.detail || "无法加载教程目录");
        if (cancelled) return;
        setCatalog(data);
        const first = data.groups[0]?.entries[0]?.path;
        if (first) {
          router.replace(`/tutorial/${first.replace(/\.md$/i, "")}`);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "无法加载教程目录");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (error) {
    return (
      <TutorialShell catalog={catalog} selected="" error={error}>
        <p className="harness-status">{error}</p>
      </TutorialShell>
    );
  }

  return (
    <TutorialShell catalog={catalog} selected="" error="">
      <p className="harness-status">正在打开教程…</p>
    </TutorialShell>
  );
}
