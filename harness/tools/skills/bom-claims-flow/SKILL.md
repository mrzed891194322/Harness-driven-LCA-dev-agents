# BOM 数量抽取 · 02 工作流（单技能）

需要时阅读。流程短：读文 → 抽题面所问 → **轻自检** → 交付。细则只读 `refs/`，勿扩写本文件。

## 工作流（按序）

1. **读文**：`refs/read-window.md`（优先 `reference.md`；小窗 `grep`→`read offset/limit`）。
2. **提取**：对照题面，交能回答所问的 `(value, unit)` 初稿（写 `workspace/artifacts/bom/claims.json`）。`unit` 对齐 produce 短符号 → `refs/units.md`。
   - 写 claims 前先锚定题意 → `refs/types.md`「题意锚定」：从 plan/题面抽出**所问对象 + 量纲 + 范围**，再去原文找对应证据行。
   - 表格 / 饼图 / 柱图：按 **legend / 行列名词** 与题面对象对齐取值（问 A 就取 A 扇区/行），勿交互补项或相邻类别。
   - 符号与形态：`value` 的正负号、数值形态须与证据原文数字一致（损失 / 负值照原文带 `-`）。
3. **轻自检**（只改确认违规；**勿过砍真 claim**）：
   - 黑名单仅 `h` / `°C` 等 → `refs/types.md`
   - 短防多报（同表邻居 / 扫参端点）→ `refs/types.md`「短防多报」
   - 单位短符号 + 硬反例 → `refs/units.md`
4. **交付**：立刻 `submit`（`status=done` + `summary` + `artifacts`）。

## 硬禁

- **禁止鼓励弃权 / 空交**：有任一原文依据可答题面时，必须交非空 `claims`；**不要** `abstained: true` + `claims: []` 当「稳妥」。
- 仅当 knowledge **完全没有**可答数字时才可空 claims；勿因自检过严清空整卷。
- 自检只删**确认**黑名单项与确认多报；吃不准是否该交 → **保留**（勿宁漏过砍）。

## 参考文档

- `harness/tools/skills/bom-claims-flow/refs/read-window.md`
- `harness/tools/skills/bom-claims-flow/refs/types.md` — 黑名单（仅 h/°C）+ 短防多报 + 题意锚定
- `harness/tools/skills/bom-claims-flow/refs/units.md` — 短符号契约 + 硬反例

有 `<rework>` 时只改所列问题后再交付。
