# BOM 数量抽取 · 02 工作流

按序执行，不扩写。

1. **读技能**：先读完本文件（含文末评分器单位同义表）。
2. **读文**：在 `harness/knowledge/inputs/` 用 `grep` 定位，再 `read`（带 offset/limit）读证据窗口；窗口不足以确认上下文（表头、图例、所属对象）时扩窗或读相关章节。
3. **锚定题意**：从题面/plan 写下所问的对象、量纲、范围；表格/图表按图例、行列名与所问对象对齐。只交题面所问的量。
4. **抽取**：写 `workspace/artifacts/bom/claims.json`，每条 claim 必有 `claim_id`，数值 claim 的 `value` 与 `unit` 成对填写。
   - `value`：原文数值，数字与正负号一致；不做单位换算，不改写数值。
   - `unit`：**照抄原文单位短语**（含限定语，如 `N`、`glass`、`of dissolved tin`）；不要压成短符号，也不要为对齐评分器同义表而改写。同义表仅说明评分器如何规范化，不是交卷目标写法。
   - **无量纲**：原文明确标为无量纲时（图注 `[-]`、文中写 `dimensionless`、或纯比值且无单位），`unit` 交字面 `"-"`（评分器占位约定，非某题金标）；原文写法（如 `[-]`）保留在 `evidence`。勿交 `null`/`[-]`/`1`/`dimensionless`。
   - `evidence`：可回源——写明文件名、位置（章节/行/表名），并逐字摘录含该数值及其单位的原文；表格须带表头、行名及单位所在位置。
   - 原文不足以直接给出该值、只能由你推断或估算时，不要编造引文：`evidence` 以 `[推断]` 开头，写明推断依据及所用原文出处。
5. **核对**：调用 `check_claims`。它只提醒，不删改 claim、不拦交卷。告警不要求清零；逐条回原文确认后再决定是否修改，禁止按告警批量删条。
6. **交付**：`submit`。

原文有可答题面的数字就交非空 claims；完全没有时才 `abstained: true` + `claims: []`。
有 `<rework>` 时只改所列问题后再交付。

---

## 评分器单位同义表（非金标）

来源：`.benchmark/bom/scorers/claim_f1.py` 的 `UNIT_NORMALIZATION`（上游 PCFBench `unit_normalization.py`）。这是**评分规则词汇表**，不是某道题的答案。`unit` 仍照抄原文短语；表只说明哪些写法会被归到同一规范族（及 value 缩放）。表中没有的单位按原文逐字比对。

规范化时另会：大小写不敏感；去空格/点/连字符；`per`→`/`；`-eq`/`eq` 统一。预测侧还会试整串、逗号前、括号前、首词。绝对质量别名（同文件 `_EXTRA_MASS`）：`kg`/`g`/`gram(s)`/`lb(s)`/`lbm`/`t`/`tonne`/`ton` 互认并按比例缩放——交付仍写原文，勿为此改写。

| 查找键（规范化后） | 规范族 | value 缩放 |
| --- | --- | --- |
| `%` / `percent` / `mass%` / `wt%` / `weight%` / `%mass` / `%wt` / `percentreduction` | percent | 1 |
| `kg/kg` | kg/kg | 1 |
| `g/kg` / `gr/kg` / `grams/kilogram` / `grams/kg` | kg/kg | 0.001 |
| `mj/kg` / `gj/t` / `gj/tonne` | mj/kg | 1 |
| `kwh/kg` / `kw.hr/kg` / `kwhr/kg` | kwh/kg | 1 |
| `kwh/ton` / `kwh/tonne` | kwh/kg | 0.001 |
| `btu/lb` / `btu/lbm` | btu/lb | 1 |
| `kgco2e/kg` / `kgco2eq/kg` / `kgco2eqperkg` / `kgco2eperkg` / `kgco2eq/1kg` / `kgco2/kg` | kgco2e/kg | 1 |
| `kgco2e/tonne` / `kgco2eq/tonne` / `kgco2e/t` | kgco2e/kg | 0.001 |
| `tonnesco2e/tonne` / `tco2e/tonne` / `tco2e/t` | kgco2e/kg | 1 |
| `kgco2e/m2` / `kgco2eq/m2` | kgco2e/m2 | 1 |
| `kgco2e/fu` / `kgco2eq/fu` | kgco2e/fu | 1 |

### 无量纲（评分约定，非金标答案）

上游同义表无此行；PCFBench 标注约定无量纲 `unit` 为字面 `"-"`（规范化后为空串，仍走 `(value, unit)` 键）。交付时：

| 原文常见写法 | 交卷 `unit` | 说明 |
| --- | --- | --- |
| `[-]` / `dimensionless` / 纯比无单位 / `1`（无量纲占位） | `"-"` | 评分契约占位；原文写法写入 `evidence` |

勿交 `null`、空串、`[-]`、`1`、`dimensionless`——这些与评分约定占位 `"-"` 对不上。
