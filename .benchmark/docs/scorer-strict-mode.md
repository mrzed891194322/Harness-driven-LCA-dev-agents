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
| `mean_f1` / `macro_f1` / `micro_f1` | **strict 汇总主结果** |
| `strict_*` | strict 明示（与上表同义，便于脚本只读 strict 前缀） |
| `ext_*` | extended **调试** |
| `n_no_output` | 有 `score_reason` 的案（无产物 / no_submit / failed 等） |

## 无法 1:1 对齐的点

1. **Text-only gold/pred**：extended 计 claim；strict 完全跳过——这是官方 extraction API 只接受 `(float, str)` 的固有限制，不是实现偏差。
2. **绝对质量 g/kg/lb**：extended 用 harness `_EXTRA_MASS`；strict 未知单位走官方 pass-through key——同一数值可能在 extended 匹配、strict 不匹配。
3. **宏平均语义**：两者均为案均 F1；strict 空空案为 0 会拉低 strict macro，extended 为 1 则抬高——与上表双空规则一致。

## 上游来源

Vendored from consult bundle:

- `materials/upstream/unit_normalization.py`
- `materials/upstream/extraction.py`

（见各文件头注释；import 改为包内相对导入。）
