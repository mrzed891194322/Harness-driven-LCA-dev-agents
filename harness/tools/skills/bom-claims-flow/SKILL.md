# BOM 数量抽取 · 02 工作流（单技能）

需要时阅读。流程短：读文 → 抽题面所问 → **轻自检（强制 MCP）** → 交付。细则只读 `refs/`，勿扩写本文件。

## 工作流（按序）

1. **读文**：`refs/read-window.md`（优先 `reference.md`；小窗 `grep`→`read offset/limit`）。
2. **提取**：对照题面，交能回答所问的 `(value, unit)` 初稿（写 `workspace/artifacts/bom/claims.json`）。`unit` 对齐 produce 短符号 → `refs/units.md`。
3. **轻自检**（只改确认违规；**勿过砍真 claim**）：
   - **强制**：先调用 MCP `bom_claims_check.check_claims`（只读告警；**禁止**指望它自动删 claim——它永不改写文件）。
   - 按返回的 `hard_errors` / `warnings` 与下列细则，**手动**改 `claims.json`：
     - 黑名单仅 `h` / `°C` 等 → `refs/types.md`
     - 证据关系局部删（多报按证据关联删条）→ `refs/types.md`「证据关系局部删」
     - 单位短符号 + 硬反例 → `refs/units.md`
   - 改完可再调一次 `check_claims` 确认；吃不准是否该交 → **保留**。
4. **交付**：立刻 `submit`（`status=done` + `summary` + `artifacts`）。宿主交卷后仍会窄硬闸黑名单单位。

## 硬禁

- **禁止鼓励弃权 / 空交**：有任一原文依据可答题面时，必须交非空 `claims`；**不要** `abstained: true` + `claims: []` 当「稳妥」。
- 仅当 knowledge **完全没有**可答数字时才可空 claims；勿因自检过严清空整卷。
- 自检只删**确认**黑名单项与确认多报；吃不准是否该交 → **保留**（勿宁漏过砍）。
- **禁止**编写/调用任何会批量自动删 claim 的脚本；MCP 与宿主检查都是只读/闸，删改只能人工按条。

## 参考文档

- `harness/tools/skills/bom-claims-flow/refs/read-window.md`
- `harness/tools/skills/bom-claims-flow/refs/types.md` — 黑名单（仅 h/°C）+ 证据关系局部删
- `harness/tools/skills/bom-claims-flow/refs/units.md` — 短符号契约 + 硬反例

有 `<rework>` 时只改所列问题后再交付（仍须先 `check_claims`）。
