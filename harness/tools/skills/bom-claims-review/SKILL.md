# BOM 数量抽取 · 审核护栏（对照长文 · 压 B2/B3 · 慎补漏）

审核者专用。**必须先读同一份 knowledge 长文**，再对照 `claims.json`；按条核对后立刻交卷，勿写成厚散文。

## 角色分工

- **executor**：从长文抽出 claims（03 挂 `bom-claims-slim`）。
- **reviewer**：读**同一份**长文（`harness/knowledge/inputs/` 下的 `reference.md` / `document_text`），**对照原文**核对；侧重点是核对，不是自己重抽一套再交卷。
- 宿主 reviewer **只读**：不能直接改产物。有问题一律 `reject`，在 `issues` 写清 `where` / `problem` / `expected`，由 executor 改写后再交。

## 强制：先读原文

- **禁止不读原文就 approve**：不得仅凭题面或 claims 字面橡皮章全过。
- **应读** knowledge 长文：按需 `read` / `grep` / 分段窗口（可参照 `bom-claims-read`）；题面未覆盖的数字/单位必须在原文找到出处再判。
- 找不到原文支持 → 按下方「删」处理，勿猜、勿换算补洞。

## 审核动作（reject 时 expected 写清要 executor 怎么改）

1. **多报 → 删（压 B2）**  
   题面未问、或原文无支持的 claim（同表邻居行、扫参端点、分解项、无关 `%` / 工时 `h` / 温度等）→ `reject`，`expected` 写明**删除**哪条（claim_id / value+unit）。

2. **单位 → 与原文一致，禁换算/改写（压 B3）**  
   `unit` 须与原文写法一致：禁止 MJ↔kWh（及其它）换算；禁止缩短/改写单位散文（勿丢 `of X` / `glass` / `per kg …`；`lbm`≠`lb`）。  
   不对 → `reject`：`expected` 写**改回原文完整单位短语**，或若无法对齐则**删**该条。同一量勿双单位双 claim。

3. **漏报 → 高门槛才补（勿滥补伤 P）**  
   仅当同时满足才可要求补：  
   - 原文**明确**出现该数值+单位；且  
   - 该量**回答题面**所问；且  
   - executor 漏交。  
   吃不准 → **不要**要求补（宁漏勿堆；滥补会伤 precision）。`expected` 须引用原文依据（短语/定位），禁止空想补数。

4. **对错**：数值/对象张冠李戴或编造 → `reject`（删或改正到原文依据）。

5. **合计**：题面要合计时交一条合计；勿拆成工序两条却无合计。

6. **交卷**：核对完立刻 `submit`（`verdict=approve|reject|…`，**必须带参**）；禁止空 `{}`。有可修 claims → `reject`，勿 `no_submit` 卡死。未用参数省略，勿传 null。

## 禁止

- 橡皮章：未读 knowledge 长文就 `approve`。
- 不读原文、只扫 claims 列表。
- 自己当抽数人再交一套 claims（除非宿主明确允许 reviewer 写产物——当前不允许）。
- 为「凑全」而要求补无明确原文依据的量。
