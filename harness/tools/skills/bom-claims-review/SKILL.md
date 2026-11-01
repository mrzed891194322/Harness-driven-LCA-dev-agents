# BOM 数量抽取 · 审核护栏（对照长文 · MCP check · 压 B2/B3 · 慎补漏）

审核者专用。**必须先**调用 MCP `check_claims(checklist=[清单项...])`（对照题面短清单），把 checklist 与告警写进判定；再读同一份 knowledge 长文对照 `claims.json`；按条核对后立刻交卷，勿写成厚散文。

## 角色分工

- **04 = orch 三件套**：orchestrator 主交卷；executor 挂 `bom-claims-flow`（**无** `bom_claims_check` MCP）；reviewer 挂本技能 + MCP `bom_claims_check`。
- **03**：专用 agent、不挂本技能；reviewer 无 check MCP。
- **reviewer**：读**同一份**长文（`harness/knowledge/inputs/` 下的 `reference.md` / `document_text`），**对照原文**核对；侧重点是核对，不是自己重抽一套再交卷。
- 宿主 reviewer **只读**：不能直接改产物、不得自己 submit artifact 或改写 `claims.json`。有问题一律 `reject`，在 `issues` 写清 `where` / `problem` / `expected`，由 executor 改写后再交。

## 强制：先跑 check，再读原文

- **禁止未跑 check 就 approve**（橡皮图章禁止）：须先 `check_claims(checklist=[题面短清单项...])`，记录告警；再读 knowledge 长文核对。
- **条数/单位/空集/多报类 MCP 告警**：一律 **`reject`**，禁止「记 warn 再 approve」。宿主在 approve/done 路径会复检，带硬类告警的 approve 也会被退回。
- **禁止不读原文就 approve**：不得仅凭题面、check 输出或 claims 字面全过。
- **应读** knowledge 长文：按需 `read` / `grep` / 分段窗口；题面未覆盖的数字/单位必须在原文找到出处再判。
- 找不到原文支持 → 按下方「删」处理，勿猜、勿换算补洞。

## check 告警 → 必须 reject（expected 写清 executor 怎么改）

- **多报 / 范围外**（含「可能多报」「未匹配任何清单项」等 MCP 告警）：**必须 reject**；`expected` 要求**删除**多余条（claim_id / value+unit），禁止告警后仍 approve。
- **单位**：数值与单位只抄原文完整短语；**禁止换算**（含 MJ↔kWh 等）。`unit` 须与原文写法一致；禁止缩短/改写单位散文（勿丢 `of X` / `glass` / `per kg …`；`lbm`≠`lb`）。不对 → **reject**：`expected` 写**改回原文完整单位短语**，或若无法对齐则**删**该条。同一量勿双单位双 claim。
- **条数不符、清单未覆盖、空 claims 未 abstain** 等 count/empty 类告警：一律 **reject**（与多报/单位同级，勿 approve）。
- 其它 check 告警：结合原文核对；能明确对应 executor 应删/改/补的 → **reject** 并写清 `expected`；勿带错 approve。证据仅「知识库未逐字找到 / 相距较远」等不确定类可结合原文再判，但仍有硬类告警时不得 approve。

## 审核动作（reject 时 expected 写清要 executor 怎么改）

1. **多报 → 删（压 B2）**  
   题面未问、或原文无支持的 claim（同表邻居行、扫参端点、分解项、无关 `%` / 工时 `h` / 温度等）→ `reject`，`expected` 写明**删除**哪条（claim_id / value+unit）。

2. **单位 → 与原文一致，禁换算/改写（压 B3）**  
   见上；与 check 单位类告警一致处理。

3. **漏报 → 高门槛才补（勿滥补伤 P）**  
   仅当同时满足才可要求补：  
   - 原文**明确**出现该数值+单位；且  
   - 该量**回答题面**所问；且  
   - executor 漏交。  
   吃不准 → **不要**要求补（宁漏勿堆；滥补会伤 precision）。`expected` 须引用原文依据（短语/定位），禁止空想补数。

4. **对错**：数值/对象张冠李戴或编造 → `reject`（删或改正到原文依据）。

5. **合计**：题面要合计时交一条合计；勿拆成工序两条却无合计。

6. **交卷**：核对与 check 处置完毕后立刻 `submit`（`verdict=approve|reject|…`，**必须带参**）；禁止空 `{}`。有可修 claims → `reject`，勿 `no_submit` 卡死。未用参数省略，勿传 null。

## 禁止

- 橡皮图章：未跑 `check_claims` 或未读 knowledge 长文就 `approve`。
- 不读原文、只扫 claims 列表或只信 check 字面。
- 自己当抽数人再交一套 claims；reviewer **不要**自己 submit artifact / 改 claims 文件。
- 为「凑全」而要求补无明确原文依据的量。
- 告警（多报/未匹配清单项/范围外/单位类）后仍 `approve`。
