# BOM 数量抽取 · 审核护栏（04 · MCP check · 压多报）

审核者专用。**必须先**调用 MCP `mcp__bom_claims_check__check_claims(checklist=[清单项...])`（对照 executor 写入的 checklist 中 `items` 或题面短清单），把 checklist 与告警写进判定；再读同一份 knowledge 长文对照 `claims.json`；按条核对后立刻交卷。

## 角色分工

- **04**：orchestrator 主交卷；executor 挂 `bom-claims-flow-04`（**无** check MCP）；reviewer 挂本技能 + MCP `bom_claims_check`。
- **03**：专用 agent、不挂本技能；reviewer 无 check MCP。
- **reviewer**：只读核对，有问题一律 `reject`；不得自己 submit artifact 或改写 `claims.json`。

## 审核口径

与挂载的 PCFBench 官方 rule 一致：`unit` 用原文短 token（与 evidence 一致，勿 silent 单复数改写）、区间中点、只抽原文直接或可清晰推导的值，不估算/不幻觉。无依据应为空 `claims`。清单 N 只用于覆盖核对，**不要求** `claims` 条数等于 N。

## 强制：先跑 check，再读原文

- **禁止未跑 check 就 approve**。
- **禁止不读原文就 approve**。

## check 告警 → reject 边界

**须 reject**（`expected` 写清 executor 怎么改）：

- **漏题面项**：清单项在原文有可答依据而 claims 未覆盖（`CHECKLIST_ITEM_UNCOVERED`）。
- **脱靶 / 清单外**（`CLAIMS_UNMATCHED_CHECKLIST`）：标签对不上任何清单项，或同一清单项内**拆分明细加总等于主值**的多余条（如 56% 与 32%+24% 拆分）→ **reject**；`expected` 要求**删除**这些 hard 条，勿整槽合并成一条除非原文只应有一条。
- **有数却空 claims**：原文有可答数字却空 `claims` → **reject**。

**勿仅因下列 MCP 告警就 reject**（结合原文再判）：

- 纯 **条数≠N**（`CLAIMS_COUNT_MISMATCH`；合法多口径、同槽多值可多于 N）。
- **`CLAIMS_SAME_SLOT_EXTRA`**：逐条核对原文支持、主问适用性和交付必要性（见下文）；有据的独立直接答案保留，有据但属于未问替代工艺/重复表达的条目仍可语义 `reject`。**勿**指令「整槽合并为 1 条」凑 N。
- **value 邻近 / 证据未逐字找到 / 相距较远** 等不确定类（对照原文裁定）。

## 主问与交付必要性（适用于所有 claims，包括无告警条）

`check` 通过只说明机械核对未发现对应问题；标签命中、evidence 找到、只有 soft 告警，都不自动等于应当独立交付。逐条回读完整段落、表头、行列标签及脚注，确认对象、阶段、条件、单位和统计口径。主条款（canonical）由题面与原文适用范围确定，不是默认第一条、最大/最小值或唯一一条。

- **替代工艺**：主问已由适用主条款覆盖，且原文明示该条为可选/替代工艺时，默认移出数值交付；题面要求全量、替代或比较，或它是唯一可答依据时保留。不能将实际采用的处理水平、对照实验当作未问替代方案，也不能仅凭脚注编号或关键词删条。
- **同温度的形态分叉**：同一工艺/阶段/来源条款下，题面只问温度而未要求逐形态回答时，重复同一温度合一条保留，保留各产品形态、时间与 temper 条件及对应原文证据。不同温度分别保留；有据的形态分叉不能仅因主值已覆盖就全删。明确要求逐形态/条件时保留区分；不做全局 `value+unit` 去重，不跨对象、指标、阶段、来源或统计口径合并。
- **独立口径**：独立来源估计、均值/标杆、实际年度施用量、不同处理水平、零值对照均可同槽多条，不因已有主值、条数多或数值可凑加总而删。区间仍按官方 rule 取中点，不为增加条数拆端点。
- **表行与旁述**：核对 annual / average annual 等统计口径和适用条件，不用邻近行或近似散文替代所问表值。nominal 或远处变体须回读上下文：仅重述已交工艺、讨论未问性能时删除；独立直接回答主问时保留。不能按金标是否收录判断。原文双单位表达不能套用“替代工艺”裁决，短单位 token 不擅自改单复数。
- **清单覆盖**：示例对象不构成无依据的全组合；共用条款可以覆盖多个对象，但不能外推到原文未支持的对象。不得用改标签、补猜测数值或强裁条数来消除告警。

**返工必须具体**：`issues` 中 `where` 定位 claim ID/字段，`problem` 写出题面范围与原文支持的替代、重复或错行关系，`expected` 明确删哪条、合到哪条、必须保留哪些条件和证据，以及哪些独立答案保留。覆盖同轮发现的问题，避免只修标签再放行。禁止“压到 N”“金标没有”“只剩 soft 所以 approve”。COUNT/SAME_SLOT 保持 soft；语义 reject 的依据是上述核实的问题，不是告警码或条数比例。

## 审核动作

1. **`CLAIMS_UNMATCHED_CHECKLIST` → 删 clear miss / sum-split 硬溢出**  
2. **所有 claims → 核对交付必要性**；收掉未问替代、合并同指标重复表达；保留有据独立答案与适用条件，不凭 soft 告警删条
3. **单位/数值 → 与官方 rule 及原文一致**；不对 → **reject** 或**删**  
4. **漏报 → 高门槛才补**  
5. **对错**：数值/对象张冠李戴或编造 → `reject`  
6. **交卷**：立刻 `mcp__submit__submit`（`verdict=approve|reject|…`，**必须带参**）

## 禁止

- 橡皮图章；自己当抽数人；为凑全而补无依据的量；为凑 N 条数而合并/删条；
- **漏题面/脱靶 hard 多报/有数却空 claims 时仍 `approve`**；宿主在 `approve` 提交时会复检 `CLAIMS_UNMATCHED_CHECKLIST` / `CHECKLIST_ITEM_UNCOVERED` / 空 claims 并拒收（**不含** soft `CLAIMS_SAME_SLOT_EXTRA`）。
