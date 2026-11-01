# BOM 数量抽取 · 02 工作流

按序执行，不扩写。单位/区间/不估算口径以挂载的 PCFBench 官方 rule 为准。

1. **定清单/N（读文前）**：只依题面列短清单「对象×所问指标」；N=len(checklist)。题面把同材料/同路径连续工序用单数量词和 and（含 respectively）问成一项时，清单只列 1 项。读文后严禁反扩清单。
2. **读原文并抽取**：按清单在 `harness/knowledge/inputs/` 用 `grep` 定位、`read` 确认，写 `workspace/artifacts/bom/claims.json`。
3. **薄规则**（N 是清单项数，不是 claim 条数上限）：
   - **区间**：原文为范围时用**中点**作 `value`（一条 claim）。
   - **并列**：同一清单项在原文有多个互不相同的口径/对照值（非同一区间两端）时可并列多条。
   - **合并**：同一清单项仅给同单位、同口径、不重叠分项且可清晰相加时，只交相加总和，不另交分项；禁止跨指标乘除。
   - **不交**：未问分项、同值换单位重复、定义常数、`value=null`、清单外。
   - **字段**：每条尽量含 `claim_id`；`value`/`unit`/`text`/`evidence` 按 spec；`unit` 用短符号。
4. **核对**：`check_claims(checklist=[清单项...])` → 有告警则改 → 再 check。多报/范围外类告警须删多余条后再 check；条数≠N 不硬卡。
5. **交付**：无文档依据则交 `claims: []`。有 `<rework>` 时只改所列问题。
