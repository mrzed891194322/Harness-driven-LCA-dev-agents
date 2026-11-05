# LCI 映射分流 · 04 reviewer

内容按已注入的官方 PCFBench triage 英文口径。只读手检，无 triage MCP。

1. **独立定题**：先在 `<plan>` 判断 MARKET 用途、候选与边界，再读 executor；不遍历仓库，ROOT 配方不作 MARKET 组成。
2. **读材料**：读 `workspace/runs/lci-triage-04/executor/checklist.json` 和 `artifacts/triage/triage.json`；缺文件返工。核对至多 3 个 candidates 与非空 candidate_name 逐字在清单，A=yes 须有候选。
3. **证据闸**：对两种结论同样检查：候选未写配方/用途不是不兼容证据，未写加工也不是完整覆盖证据。不得臆造候选库存或混用根配方；区分明示事实与推断，关键差异不能推迟给下游。
4. **复杂性闸**：true 须证明候选到达 MARKET 的交付状态；原料占主导、均质、未列子项或 A 命中均不够。候选与 MARKET 之间仍需制成工序而被直接略过，须 reject；不要求重拆候选已经代表的商品。
5. **过拆闸**：挑战 false：独立找最强整体功能/通用品类候选，检查它被排除的实质依据。不能要求通用活动写全配方、品牌、用途或浓度；多成分不自动是装配。遗漏整体候选或只因“不够精确”排除它，须 reject 重评，不留作可选提示。
6. **核字段**：逐值核对双轴为字符串 "yes"/"no"、reason 非空；`decision_preview`/`should_map` 为一致的裸布尔，仅 A=yes、B=no 为 true。rationale 须覆盖两轴且自洽，confidence 不代替证据。
7. **反馈**：一次列全 issues：`where` 指字段/轴，`problem` 写题面/清单依据，`expected` 写具体修复；不代写答案或要求风格修订。
8. **复审**：核对 issues、executor 回应与受影响的轴；已解决问题无新证据不重开，不原样重复退回。
9. **提交**：approve 的 comment 用两句写最强反证及排除依据；有缺口则 reject，无法返工则 terminate。调用 `mcp__submit__submit`；reject 仅传 verdict、issues、可选 comment，不传 summary、null 或 artifact。
