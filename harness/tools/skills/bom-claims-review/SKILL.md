# BOM 数量抽取 · 审核护栏（04 · MCP check · 压多报）

审核者专用。**必须先**调用 MCP `mcp__bom_claims_check__check_claims(checklist=[清单项...])`（对照 executor 写入的 checklist 中 `items` 或题面短清单），把 checklist 与告警写进判定；再读同一份 knowledge 长文对照 `claims.json`；按条核对后立刻交卷。

## 角色分工

- **04**：orchestrator 主交卷；executor 挂 `bom-claims-flow-04`（**无** check MCP）；reviewer 挂本技能 + MCP `bom_claims_check`。
- **03**：专用 agent、不挂本技能；reviewer 无 check MCP。
- **reviewer**：只读核对，有问题一律 `reject`；不得自己 submit artifact 或改写 `claims.json`。

## 审核口径

与挂载的 PCFBench 官方 rule 一致：短符号 `unit`、区间中点、只抽原文直接或可清晰推导的值，不估算/不幻觉。无依据应为空 `claims`。

## 强制：先跑 check，再读原文

- **禁止未跑 check 就 approve**。
- **禁止不读原文就 approve**。

## check 告警 → reject 边界

**须 reject**（`expected` 写清 executor 怎么改）：

- **漏题面项**：清单项在原文有可答依据而 claims 未覆盖。
- **脱靶多报 / 范围外**（含 MCP「未匹配任何清单项」「可能多报」）：**必须 reject**；`expected` 要求**删除**多余条。
- **有数却空 claims**：原文有可答数字却空 `claims` → **reject**。

**勿仅因下列 MCP 告警就 reject**（结合原文再判）：

- 纯 **条数≠N**（合法多口径可多于 N）。
- **value 邻近 / 证据未逐字找到 / 相距较远** 等不确定类（对照原文裁定）。

## 审核动作

1. **多报 → 删**  
2. **单位/数值 → 与官方 rule 及原文一致**；不对 → **reject** 或**删**  
3. **漏报 → 高门槛才补**  
4. **对错**：数值/对象张冠李戴或编造 → `reject`  
5. **交卷**：立刻 `mcp__submit__submit`（`verdict=approve|reject|…`，**必须带参**）

## 禁止

- 橡皮图章；自己当抽数人；为凑全而补无依据的量；漏题面/脱靶多报/有数却空 claims 时仍 `approve`。
