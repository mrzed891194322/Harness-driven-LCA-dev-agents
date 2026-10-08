import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata = {
  title: "Harness LCA",
  description: "Pi SDK unified runtime control panel",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="app-shell">
          <header className="app-header">
            <h1>Harness LCA</h1>
            <p>Pi SDK 唯一运行时 · 自带密钥（BYOK）</p>
          </header>
          <nav className="nav-row">
            <Link href="/settings">设置与初始化</Link>
            <Link href="/plan">LCA 计划</Link>
            <Link href="/runs">运行详情</Link>
            <Link href="/results">结果与历史</Link>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
