# Claim F1 strict vs extended

**主结果=严格，扩展=调试。**

## 目的

- **strict**（主结果）：vendored 官方 `pcfbench_official/{unit_normalization,extraction}.py`，仅 `(value, unit)` claim，匹配算法与 upstream `extraction._match_extraction_claims` 一致。
- **extended**（调试）：现有 `claim_f1.py`——含 `_EXTRA_MASS`（g/kg 绝对质量）、text-only claim 的文本匹配、与 PCFBench 相同的 `unit_candidates` 与 multiset Counter 匹配。

## 行级映射

| extended (`claim_f1.py`) | strict (`claim_f1_strict.py` + vendored) |
| --- | --- |
| `UNIT_NORMALIZATION` + `_EXTRA_MASS` | 仅 `UNIT_NORMALIZATION`（官方表） |
| `claim_key` → Counter multiset | `_match_extraction_claims` 贪心按 GT 顺序 |
| pred 侧 `unit_candidates` + `prefer_units` | pred 侧 `_unit_candidates` + `gt_units` 集合 |
| text-only → `("text", norm_text)` | **忽略**（不参与 strict n_gold/n_pred） |
| 双空 claims → F1=1 | 双空 (value,unit) → F1=0（与 `run_claim_f1` 全零分母一致） |
| `zero_pred_scores`：n_gold=len(all claims) | n_gold=len(value+unit claims only) |

## score_batch 字段

| 字段 | 含义 |
| --- | --- |
| `f1` / `precision` / `recall` / `n_gold` / `n_pred` / `matched` | **strict 主结果**（兼容旧字段名，语义已指向严格） |
| `mean_f1` / `macro_f1` / `micro_f1` | **strict 汇总主结果**（headline = strict micro F1） |
| `strict_*` | strict 明示（与上表同义，便于脚本只读 strict 前缀） |
| `ext_*` | extended **调试** |
| `n_no_output` | 有 `score_reason` 的案（无产物 / no_submit / failed 等） |
| `n_f1_eq_1` | strict F1=1 且非 no-output 的案数 |
| `n_over_report` | strict n_pred > n_gold 且 F1<1 的案数 |

## claims.json 路径（score_batch / rescore_history）

1. **首选**：`<run_dir>/runs/_run/artifacts/bom/claims.json`（当前 bom-extract 工作区交付，与 `layout.produce_target` 一致）。
2. **回退**：`<run_dir>/artifacts/bom/claims.json`（历史 batch 快照，仅复制 workspace `artifacts/` 的旧布局）。
3. 两者皆无 → claim 套件走 F1=0（`score_reason` / `no_artifact`），仍计入分母。

行级 `pred_source=legacy_artifacts_bom` 表示使用了回退路径。

## `--subset`

`--subset FILE`：`FILE` 每行一个 `case_id`（可 `#` 注释）。`summary.json` 在完整 `aggregate` 之外增加 `summary.subset`（同结构，仅 subset 内行）。

## 无法 1:1 对齐的点

1. **Text-only gold/pred**：extended 计 claim；strict 完全跳过——这是官方 extraction API 只接受 `(float, str)` 的固有限制，不是实现偏差。
2. **Gold/pred 空 unit 字符串**：与 upstream 一致，凡 `value is not None` 的 claim 都进入 strict 计数与匹配；`unit` 为 `""` / 缺字段时按 `""` 传入官方 matcher（`extraction.py` L80：`gt_normalized = [normalize_value_and_unit(v, u) for v, u in gt_claims]`；L36–37：`if not unit: return [unit]`）。`value is None` 的 text-only 行 upstream 不会 `float`，harness 同样跳过。
3. **绝对质量 g/kg/lb**：extended 用 harness `_EXTRA_MASS`；strict 未知单位走官方 pass-through key——同一数值可能在 extended 匹配、strict 不匹配。
4. **宏平均语义**：两者均为案均 F1；strict 空空案为 0 会拉低 strict macro，extended 为 1 则抬高——与上表双空规则一致。

## 上游来源

Vendored from consult bundle:

- `materials/upstream/unit_normalization.py`
- `materials/upstream/extraction.py`

（见各文件头注释；import 改为包内相对导入。）
