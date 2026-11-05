# LCI 映射分流 · 04 executor

内容按已注入的官方 PCFBench triage 英文口径；本技能只规定如何形成判断与交付。

1. **定题并找候选**：读 `<plan>` 的 MARKET 与 picklist，只在计划内检索，不遍历仓库、不查询 openLCA。ROOT 只解释对象，不把根配方转作本节点组成。先找整个采购项的用途与通用品类，再找同族材料、加工形态；保留至多 3 个逐字存在于 picklist 的活动名，不只搜品牌或组分。
2. **填写双轴**：A 判断最强候选能否合理代表整个采购项的 LCI，写覆盖依据与剩余缺口；合理代理不要求精确配方或实物使用性能相同，只有原料/组分覆盖也不等于成品覆盖。B 独立判断是否必须先拆出子材料或制成活动，说明拆分补上什么，或为何候选已代表交付形态、无需进一步制成。单一材质不免除加工检查；候选已代表的商品生产链不重拆。区分题面事实、活动名信息与推断，不编造库存或合成路线。
3. **合成并存 checklist**：写 `workspace/runs/lci-triage-04/executor/checklist.json`：`axis_a={candidates, reasonable_direct_match, reason}`、`axis_b={must_decompose_first, reason}`。`axis_a.candidates` 是至多 3 个名称字符串的数组；两轴判断值为字符串 "yes"/"no"，reason 各一句依据。`decision_preview` 为裸布尔，仅 A=yes 且 B=no 为 true；无同名、配方精度差异或“均质商品”均不能单独决定结论。
4. **写产物并自查**：写 `artifacts/triage/triage.json`，`should_map` 与预览一致，`rationale` 各用一句覆盖 A/B；可选 `candidate_name` 须逐字来自 picklist，confidence 不作理由。检查候选、字段类型、两轴与结论一致后结束，不调用 submit。
5. **返工**：逐项回应 reviewer issues，同步 checklist 与产物；记录实质改动或不采纳的题面依据，不靠改措辞消除缺口。
