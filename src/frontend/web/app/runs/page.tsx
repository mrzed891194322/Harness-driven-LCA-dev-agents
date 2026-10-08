"use client";

import { useEffect, useState } from "react";

export default function RunsPage() {
  const [manifest, setManifest] = useState<Record<string, unknown>>({});

  useEffect(() => {
    const load = () =>
      fetch("/api/workflow/manifest")
        .then((r) => r.json())
        .then(setManifest);
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <h2>运行详情</h2>
      <pre style={{ background: "#f4f4f4", padding: 16, overflow: "auto" }}>
        {JSON.stringify(manifest, null, 2)}
      </pre>
    </div>
  );
}
