# 单位：对齐 produce / schema 短符号（含硬反例）

契约以 **`.benchmark/bom/harness/specs/bom-claims.yaml`** 为准：`unit` 用短符号（`g` / `kg` / `%` / `lbs` / `kg/ha` / `MJ/kg` 等），与 exact_tuple / PCFBench `unit_norm` 金标对齐。

## 规则

- **交付短符号**：从原文识别量纲后写成 schema 短符号；**不要**把整句单位散文（`kg fresh tomatoes per kg polpa`、`% of dissolved tin`、`MJ nre/kg PET`…）原样塞进 `unit`。
- **禁止量纲换算**：勿 MJ↔kWh、lbs↔kg、parts↔kg/kg；数值保持原文，只规范单位写法。
- 同一物料同一量只留一条 `(value, unit)`；原文并列双单位时只留主写那一档对应的短符号。
- 上下界 a–b → 拆成两端点两条；`value` 必须是数。

## 硬反例（必须避免）

1. **`parts` ≠ `kg/kg`**：原文是 `parts` 就交 `parts`（或题面/金标等价短符号），**禁止**擅自改成 `kg/kg` / `g/g`。
2. **上下界勿交中点**：给 a–b → 交两端点；**禁止**只交 `(a+b)/2`。
3. **勿漏同段精确量**：窗口内精确数（例：`463.4 kg/ha`）若答题面必须交；`unit` 写 `kg/ha`（短符号），勿漏这条。
4. **勿交完整原文单位短语当 unit**：与 `f4ff815` 失败实验相反——短语会与规范化金标错配；修饰语可写进 `text`/`evidence`，`unit` 仍短符号。
