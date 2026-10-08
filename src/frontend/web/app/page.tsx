import Link from "next/link";

export default function HomePage() {
  return (
    <nav style={{ display: "flex", gap: 16 }}>
      <Link href="/settings">设置与初始化</Link>
      <Link href="/plan">LCA 计划</Link>
      <Link href="/runs">运行详情</Link>
      <Link href="/results">结果与历史</Link>
    </nav>
  );
}
