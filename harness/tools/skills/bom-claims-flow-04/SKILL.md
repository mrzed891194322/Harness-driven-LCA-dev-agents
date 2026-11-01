# BOM 数量抽取 · 04 executor

按序执行。单位/区间/不估算口径以挂载的 PCFBench 官方 rule 为准。

1. **题面契约（读文前）**：只依题面把清单写入 user 注入里给出的 checklist 路径：`{"items":["对象×所问指标", ...]}`。读文后再写 claims；清单不进 claims schema。
2. **定清单/N**：N=len(items)；题面 and/respectively 合并规则同 02 flow。
3. **读原文并抽取**：按清单在 `harness/knowledge/inputs/` 定位、确认，写 `workspace/runs/_run/artifacts/bom/claims.json`。
4. **对象×指标**：只答题面所问；不因同文纳入题外对象，也不无据排除对照/同行对象。
5. **区间**：范围用**中点**一条；题面问单值且原文有作者代表值时用代表值。
6. **合并/不交**：同 02 flow（可清晰相加则一条总和；不交题外/重复/清单外）。
7. **交付**：无依据交 `claims: []`。写完 **勿** 调用 `mcp__bom_claims_check__check_claims`（核对由 reviewer + MCP）。有 `<rework>` 时只改所列问题。
