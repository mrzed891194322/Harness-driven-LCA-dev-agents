"use client";

import { useEffect, useState } from "react";

export default function PlanPage() {
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch("/api/plan")
      .then((r) => r.json())
      .then((d) => setContent(d.content ?? ""))
      .catch(() => setContent(""));
  }, []);

  async function save() {
    await fetch("/api/plan", {
      method: "PUT",
      headers: { "Content-Type": "text/plain" },
      body: content,
    });
    setStatus("已保存");
  }

  return (
    <div>
      <h2>LCA 计划</h2>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={24}
        style={{ width: "100%", fontFamily: "monospace" }}
      />
      <div style={{ marginTop: 12 }}>
        <button type="button" onClick={save}>保存计划</button>
        <span style={{ marginLeft: 12 }}>{status}</span>
      </div>
      <p style={{ marginTop: 16, color: "#666" }}>
        保存计划后，在控制面板完成初始化检查，再执行 whole-lca / revise-lca。运行进度见「运行详情」，报告见「LCA评估结果」。
      </p>
    </div>
  );
}
