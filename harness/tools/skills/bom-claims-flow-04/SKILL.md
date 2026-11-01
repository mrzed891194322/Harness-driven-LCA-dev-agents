# BOM 数量抽取 · 04 executor

按序执行。单位/区间/不估算口径以挂载的 PCFBench 官方 rule 为准。

1. **题面契约（读文前）**：只依题面把清单写入 user 注入里给出的 checklist 路径：`{"items":["对象×所问指标", ...]}`。读文后再写 claims；清单不进 claims schema。
2. **定清单**：`N=len(items)` 是**核对覆盖**用的清单长度（对象×指标条数），**不是** claims 条数配额。同一清单项在原文有多个独立有据数值时，可写多条 claim；**勿**为凑 `claims 条数 = N` 而合并或删条。题面 and/respectively 合并规则同 02 flow。
3. **读原文并抽取**：按清单在 `harness/knowledge/inputs/` 定位、确认，写 `workspace/runs/_run/artifacts/bom/claims.json`。
4. **对象×指标**：只答题面所问；不因同文纳入题外对象，也不无据排除对照/同行对象。
5. **区间**：范围用**中点**一条；题面问单值且原文有作者代表值时用代表值。
6. **合并/不交**：同 02 flow（可清晰相加则一条总和；不交题外/重复/清单外）。
7. **`unit` 字段**：写原文里该数值旁的**短单位 token，与原文一致**（如原文 `1.32lbs` → `unit` 用 `lbs`，**勿** silent 改成 `lb` 或其它单复数/别名）。「短符号」指原文短写法，不是强行单数化或 scorer 表归一。
8. **交付**：无依据交 `claims: []`。写完 **勿** 调用 `mcp__bom_claims_check__check_claims`（核对由 reviewer + MCP）。有 `<rework>` 时只改所列问题。
