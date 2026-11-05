# LCI 映射分流 · 04 reviewer

内容按已注入的官方 PCFBench triage 英文口径。只读手检，无 triage MCP。

1. **独立定题**：先在 `<plan>` 判断 MARKET 用途、候选与边界，再读 executor；不遍历仓库，ROOT 配方不作 MARKET 组成。
2. **读材料**：读 `workspace/runs/lci-triage-04/executor/checklist.json` 和 `artifacts/triage/triage.json`；缺文件返工。核对至多 3 个 candidates 与非空 candidate_name 逐字在清单，A=yes 须有候选。
3. **证据闸**：核对最强候选的覆盖依据与缺口。判断 LCI 代表性，不要求候选实物可替换 MARKET 完成工艺；性能、官能团或用途差异须联系生产/材料边界，不能直接否定代理。picklist 是活动名清单，不是库存表；其中同时出现原料与成品，不证明前者/某工序已包含在候选内。executor 若把这类推断写成确定库存，须 reject 要求删除该断言后重判；同样不能臆造合成路线支持 false。
4. **复杂性闸**：挑战 true：单一材质也能拆成材料加制成活动。若已指出候选到 MARKET 之间存在未覆盖的制造工序，却又以“无独立零件”“只是后加工”排除反证，须 reject；不能只在 comment 承认缺口后仍批准。不重拆候选已代表的商品生产链。
5. **过拆闸**：挑战 false：独立找最强整体/通用品类候选，把排除理由改写为具体 LCI 缺口。不能只因物质已知、配方未写全或候选不能满足实物使用性能而排除通用代理；检查拆分是否真的补上该缺口。遗漏整体候选或仅作精度争论，须 reject 重评，不留作可选提示。
6. **核字段**：实际读取每个字段，不用语义近似代替结构核查：`axis_a.candidates` 是至多 3 个名称字符串的数组；双轴为字符串 "yes"/"no"，reason 非空；`decision_preview`/`should_map` 为一致的裸布尔，仅 A=yes、B=no 为 true。缺失、错位、类型错误须 reject。rationale 须覆盖两轴且自洽，confidence 不代替证据。
7. **反馈**：一次列全 issues：`where` 指字段/轴，`problem` 写题面/清单依据，`expected` 写具体修复；不代写答案或要求风格修订。
8. **复审**：核对 issues、executor 回应与受影响的轴；已解决问题无新证据不重开，不原样重复退回。
9. **提交**：approve 的 comment 用两句写最强反证及排除依据；有缺口则 reject，无法返工则 terminate。调用 `mcp__submit__submit`；reject 仅传 verdict、issues、可选 comment，不传 summary、null 或 artifact。
