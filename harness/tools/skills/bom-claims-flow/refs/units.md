# 单位：只抄不译 / 不换算（含硬反例）

## 规则

- `unit` **照抄原文完整短语**：勿翻译、勿缩短、勿改写量纲名（勿丢 `of X` / `glass` / `per kg …` / `nre` 等）。
- **禁止换算**：勿 MJ↔kWh、lbs↔kg、parts↔kg/kg 等；原文写什么就交什么。
- 同一物料同一量只留一条 `(value, unit)`；原文并列双单位时只留主写那一档。
- 交付写原文单位；不要为对齐 scorer 改写成别的符号族。

## 硬反例（必须避免）

1. **`parts` ≠ `kg/kg`**：原文是 `parts`（或 `parts per …`）就交 `parts`，**禁止**改成 `kg/kg` / `g/g` 等。
2. **上下界勿交中点**：题面/原文给 a–b 或上下界 → **拆成两端点两条**（`value=a` 与 `value=b`）；**禁止**只交 `(a+b)/2` 一条代替。
3. **勿漏同段精确量**：证据窗口里已出现的精确数（例：`463.4 kg/ha`）若答题面，必须交；不要只交粗值/邻近行而漏关键精确量。
4. **单位散文勿砍**：`% of dissolved tin`、`MJ nre/kg PET`、`g/g glass`、`kg fresh tomatoes per kg polpa` 等须整句照抄，勿缩成 `%` / `MJ/kg` / `g/g` / `kg/kg`。
