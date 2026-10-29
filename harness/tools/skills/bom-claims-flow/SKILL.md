# BOM 数量抽取 · 02 自检工作流（单技能）

需要时阅读。本技能 = **提取 → 初稿 → 自检硬规则 → 不合则改 → 交付**。细则只读下方参考文档，勿把护栏扩写进本文件。

## 工作流（按序）

1. **读文**：按 `refs/read-window.md` 打开 `harness/knowledge/inputs/`（优先 `reference.md`）；只取证据窗口。
2. **提取 / 初稿**：对照 `<plan>` 题面，只抽能回答所问的 `(value, unit)`；写出 `workspace/artifacts/bom/claims.json` 初稿。
3. **自检硬规则**（必做，对照参考文档）：
   - 类型 / 黑名单 → `refs/types.md`
   - 单位只抄不译、不换算 → `refs/units.md`
4. **不合则改**：删黑名单与题面未问项；单位改回原文短语；仍无依据则删该条（宁漏勿堆）。
5. **交付**：通过自检后立刻 `submit`（`status=done` + `summary` + `artifacts`）。信息不足则 `abstained: true` 且 `claims: []`，勿编造。

## 参考文档（短路由）

- `harness/tools/skills/bom-claims-flow/refs/read-window.md` — 读文档窗口
- `harness/tools/skills/bom-claims-flow/refs/types.md` — 可交类型 / 黑名单
- `harness/tools/skills/bom-claims-flow/refs/units.md` — 单位只抄

有 `<rework>` 时只改所列问题，再走 3→5。
