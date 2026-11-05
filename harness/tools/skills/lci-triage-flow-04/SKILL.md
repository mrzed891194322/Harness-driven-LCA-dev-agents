# LCI 映射分流 · 04 executor

内容按已注入的官方 PCFBench triage 英文口径；本技能只规定执行顺序。

1. **定题**：读完整 MARKET 描述与题面 picklist；ROOT MATERIAL CONTEXT 只帮助解释，不替换判定对象。不查询 openLCA。
2. **找候选**：按名称、同族和同功能检索 picklist，保留至多 3 个逐字存在的活动名；无精确同名不能直接判 false，不凭记忆补活动。
3. **Axis A**：判断候选是否覆盖整个 MARKET 的材料、功能和加工状态。近义或同族命中须说明为何可直接代表，而非只代表原料或某一组分；解释不了则 `reasonable_direct_match=no`。
4. **查聚合**：多供应源、牌号或路线聚合须核对候选覆盖范围；仅列通用商品代理不算通过 A。供应源数量本身不定结论，须说明聚合是否隐藏候选不能代表的实质差异。
5. **Axis B**：独立判断 `must_decompose_first`：需拆则指出题面支持的子组分及候选覆盖缺口；无需拆则说明该活动为何已覆盖 MARKET 的组成与加工边界。「单一、均质、可贸易中间品」不足为据。
6. **反查过拆**：package、packaging、additives、flux 或配方名称不证明多部件装配；已有同族/同功能活动能代表整体且无实质拆分需求时，A=yes、B=no。不能仅因有多种成分或无品牌同名判需拆。
7. **存 checklist**：先写 `workspace/runs/lci-triage-04/executor/checklist.json`：`axis_a={candidates, reasonable_direct_match, reason}`、`axis_b={must_decompose_first, reason}`、布尔 `decision_preview`。两轴取 yes/no，reason 各一句题面与清单依据；仅 A=yes 且 B=no 时预览为 true。
8. **写产物**：写 `artifacts/triage/triage.json`，`should_map` 与预览一致，`rationale` 各用一句覆盖 A/B；可选候选名须来自清单，confidence 不作理由。核对字段类型和结论自洽；不调用 submit。
9. **返工**：逐项回应 reviewer issues，同步 checklist 与产物；记录修改的轴或不采纳的题面依据，不靠改措辞消除实质问题。
