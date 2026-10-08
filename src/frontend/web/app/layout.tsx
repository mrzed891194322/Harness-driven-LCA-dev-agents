import type { ReactNode } from "react";

export const metadata = {
  title: "Harness LCA",
  description: "Pi SDK unified runtime control panel",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, padding: 24 }}>
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ margin: 0 }}>Harness LCA</h1>
          <p style={{ color: "#555" }}>Next.js + FastAPI · Pi SDK 唯一运行时</p>
        </header>
        {children}
      </body>
    </html>
  );
}
