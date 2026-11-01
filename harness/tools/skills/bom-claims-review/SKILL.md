# BOM 数量抽取 · 审核护栏（对照长文 · MCP check · 压 B2/B3 · 慎补漏）

审核者专用。**必须先**调用 MCP `check_claims(checklist=[清单项...])`（对照题面短清单；04 可对照 executor 写入的 `checklist.json` 中 `items`），把 checklist 与告警写进判定；再读同一份 knowledge 长文对照 `claims.json`；按条核对后立刻交卷，勿写成厚散文。

## 角色分工

- **04 = orch 三件套**：orchestrator 主交卷；executor 挂 `bom-claims-flow`（**无** `bom_claims_check` MCP）；reviewer 挂本技能 + MCP `bom_claims_check`。
- **03**：专用 agent、不挂本技能；reviewer 无 check MCP。
- **reviewer**：读**同一份**长文（`harness/knowledge/inputs/` 下的 `reference.md` / `document_text`），**对照原文**核对；侧重点是核对，不是自己重抽一套再交卷。
- 宿主 reviewer **只读**：不能直接改产物、不得自己 submit artifact 或改写 `claims.json`。有问题一律 `reject`，在 `issues` 写清 `where` / `problem` / `expected`，由 executor 改写后再交。

## 同尺四口径（04；与 flow 04 专段同词）

1. **对象×指标×分母/边界匹配**：不因同文纳入，也不无据排除对照/同行对象。
2. **单位**：仅当题面指定目标单位且原文无该单位值时，按精确物理常数同量纲换算，`value` 写换算后值，`evidence` 以 `[推断]` 开头写原文引文+算式；禁只换单位标签、禁外部经验系数。
3. **区间**：区间=一项证据，不拆两端凑条数；题面问单值且原文有作者代表值→交代表值；否则按题面形态交一条。
4. **abstain**：仅在所问量全文无直接依据；部分缺口在 `text` 注明，不清空。

## 强制：先跑 check，再读原文

- **禁止未跑 check 就 approve**（橡皮图章禁止）：须先 `check_claims(checklist=[题面短清单项...])`，记录告警；再读 knowledge 长文核对。
- **禁止不读原文就 approve**：不得仅凭题面、check 输出或 claims 字面全过。
- **应读** knowledge 长文：按需 `read` / `grep` / 分段窗口；题面未覆盖的数字/单位必须在原文找到出处再判。
- 找不到原文支持 → 按下方「删」处理；换算须符合上②。

## check 告警 → reject 边界

**须 reject**（`expected` 写清 executor 怎么改）：

- **漏题面项**：清单项在原文有可答依据而 claims 未覆盖。
- **脱靶多报 / 范围外**（含 MCP「未匹配任何清单项」「可能多报」）：**必须 reject**；`expected` 要求**删除**多余条。
- **有数却 abstain**：原文有可答数字却 `abstained: true` 或空 claims → **reject**。

**勿仅因下列 MCP 告警就 reject**（结合原文再判，可记 warn 后 approve 若原文支持）：

- 纯 **条数≠N**（合法并列、区间、多口径可多于 N）。
- **abstained 与条数≠N**  alone（真 abstention 题）。
- **单位短语 / value 邻近 / 证据未逐字找到 / 相距较远** 等不确定类（对照原文裁定；② 允许的 `[推断]`+算式换算不算单位违规）。

## 审核动作（reject 时 expected 写清要 executor 怎么改）

1. **多报 → 删（压 B2）**  
   题面未问、或原文无支持的 claim → `reject`，`expected` 写明**删除**哪条。

2. **单位 → 与②及原文一致**  
   禁只换标签；不对 → **reject**：改回原文短语、合法 `[推断]`+算式，或**删**该条。

3. **漏报 → 高门槛才补**  
   仅当原文**明确**出现、**回答题面**、executor 漏交时才要求补；吃不准 → 不要补。

4. **对错**：数值/对象张冠李戴或编造 → `reject`。

5. **交卷**：核对与 check 处置完毕后立刻 `submit`（`verdict=approve|reject|…`，**必须带参**）；禁止空 `{}`。

## 禁止

- 橡皮图章：未跑 `check_claims` 或未读 knowledge 长文就 `approve`。
- 自己当抽数人再交一套 claims；reviewer **不要**自己 submit artifact / 改 claims 文件。
- 为「凑全」而要求补无明确原文依据的量。
- 漏题面 / 脱靶多报 / 有数却 abstain 时仍 `approve`。
