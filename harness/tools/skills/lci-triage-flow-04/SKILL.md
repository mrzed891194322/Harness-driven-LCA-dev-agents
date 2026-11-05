# LCI 映射分流 · 04 executor

内容按已注入的官方 PCFBench triage 英文口径；本技能只规定执行顺序。

1. **定题**：读 `<plan>` 的 MARKET 与 picklist，在计划内检索，不遍历仓库。ROOT 仅解释对象，不能把根配方转作本节点组成；不查询 openLCA。
2. **找候选**：先查整体用途与通用品类，再查同族材料和加工形态；不要只搜品牌或组分名。保留至多 3 个逐字存在于 picklist 的活动名，不编造活动。
3. **Axis A**：判断活动能否合理代表整个采购项，而非精确复现配方。通用功能/化学品类也是候选，不要求名称写全品牌、用途、浓度；但只有原料或某一组分的覆盖不足以代表成品。
4. **验证代理**：指出 MARKET 与最强候选的关键差异及其是否改变材料、加工终点或生产边界。近义命中、同源牌号不能直接证明覆盖；区分题面事实与推断，不从候选名臆造工艺，也不把实质差异留待下游解决。
5. **Axis B**：独立判断是否必须先拆：需拆须指出候选不能代表的组成/加工边界；无需拆须说明候选代表的实际商品。均质、可贸易或题面未列子项均不充分；也不因每种商品都有上游工序就拆。
6. **反查过拆**：制剂、功能包、包装或浆料不自动等于多部件装配。先评估通用同族/同功能活动对整体的合理代表性；配方比例、稀释或多个成分本身不否定它。若仍判 false，说明最强整体候选为何实质不适用，不能只说不够精确。
7. **存 checklist**：先写 `workspace/runs/lci-triage-04/executor/checklist.json`：`axis_a={candidates, reasonable_direct_match, reason}`、`axis_b={must_decompose_first, reason}`。两轴取 yes/no，reason 各一句依据；`decision_preview` 直接填 true/false，不能包成对象，仅 A=yes 且 B=no 为 true。
8. **写产物**：写 `artifacts/triage/triage.json`，`should_map` 与预览一致，`rationale` 各用一句覆盖 A/B；可选候选名须来自清单，confidence 不作理由。核对类型与结论，不调用 submit。
9. **返工**：逐项回应 reviewer issues，同步 checklist 与产物；记录改动或不采纳的题面依据，不靠改措辞消除实质问题。
