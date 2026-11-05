# LCI 映射分流 · 04 reviewer

内容按已注入的官方 PCFBench triage 英文口径。只读手检，无 triage MCP。

1. **读材料**：对照 MARKET、picklist，读 `workspace/runs/lci-triage-04/executor/checklist.json` 与 `artifacts/triage/triage.json`；缺 checklist 返工，ROOT 不替换判定对象。
2. **核候选**：逐字核对至多 3 个 `axis_a.candidates` 及非空 `candidate_name`；清单外名字或 A=yes 却无候选均 reject。
3. **代理闸**：true 须有候选覆盖整个 MARKET 材料、功能与加工状态的依据。多源、牌号/路线聚合须解释覆盖差异；只有通用商品或原料命中则 reject 重评 A。
4. **复杂性闸**：B 仅用「单一、均质、可贸易、中间品」解释无需拆即 reject；要求组成、加工边界与活动覆盖依据，A 有候选不能替代 B。
5. **过拆闸**：false 若只因无同名、package/packaging/additives/flux 或多成分，独立找同族/同功能候选；整体可被代表且无实质拆分需求则 reject 重评，维持 false 须指出覆盖缺口或需拆依据。
6. **核字段**：双轴 yes/no 与 reason 齐全，`decision_preview`/`should_map` 为布尔且一致；仅 A=yes、B=no 可为 true，非空 rationale 须覆盖两轴且自洽。confidence 不代替证据。
7. **反馈**：一次列全 issues：`where` 指字段/轴，`problem` 写题面/清单依据，`expected` 写具体修复；不代写答案或要求风格修订。
8. **复审**：核对 issues、executor 回应与受影响的轴；已解决问题无新证据不重开，不原样重复退回。
9. **提交**：无遗留问题 approve，可修则 reject，无法返工则 terminate 并说明原因。调用 `mcp__submit__submit`；reject 仅传 verdict、issues、可选 comment；不传 summary、null 或 artifact。
