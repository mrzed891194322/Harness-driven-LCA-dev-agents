# LCI 映射分流 · 04 reviewer

内容按已注入的官方 PCFBench triage 英文口径。只读手检，无 triage MCP。

1. **独立定题**：先在 `<plan>` 内判断 MARKET 的整体用途、最强候选与边界，再读 executor 理由；不遍历仓库，不把 ROOT 配方转作 MARKET 组成。
2. **读材料**：读 `workspace/runs/lci-triage-04/executor/checklist.json` 和 `artifacts/triage/triage.json`；缺文件返工。核对至多 3 个 candidates 与非空 candidate_name 逐字在清单，A=yes 须有候选。
3. **代理闸**：挑战 true：近义或牌号相近不证明加工终点/生产边界等价。关键差异须解释；候选名不能证明完整工艺覆盖。混用根配方、把推断说成题面事实或将实质差异推迟给下游，均须纠正后重评。
4. **复杂性闸**：true 的 B 仅凭均质、可贸易、未列子项或 A 有命中即 reject；要求实际商品与候选边界依据。不要把可想象的上游工序或未明示添加物当作必须拆分的证据。
5. **过拆闸**：挑战 false：独立找最强整体功能/通用品类候选，检查它被排除的实质依据。不能要求通用活动写全配方、品牌、用途或浓度；多成分不自动是装配。遗漏整体候选或只因“不够精确”排除它，须 reject 重评，不留作可选提示。
6. **核字段**：实际读取双轴 yes/no、reason；逐值核对 `decision_preview` 和 `should_map` 都是裸布尔且一致，仅 A=yes、B=no 为 true。非空 rationale 须覆盖两轴且自洽；confidence 不代替证据。
7. **反馈**：一次列全 issues：`where` 指字段/轴，`problem` 写题面/清单依据，`expected` 写具体修复；不代写答案或要求风格修订。
8. **复审**：核对 issues、executor 回应与受影响的轴；已解决问题无新证据不重开，不原样重复退回。
9. **提交**：无遗留问题 approve，可修则 reject，无法返工则 terminate 并说明原因。调用 `mcp__submit__submit`；reject 仅传 verdict、issues、可选 comment；不传 summary、null 或 artifact。
