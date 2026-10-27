# PCFBench Task1/2/3 · 01 真薄（机制验跑）

目标：**完整工作流链路**可复跑（import → 01 orch → 交卷 → scorer → run_batch），DeepSeek 各 30 案是验机制，不先追准度。

| 任务 | 官方 | stem | cases-root | 产物 | 主指标 |
|------|------|------|------------|------|--------|
| T1 组成 | task1_decomposition | `bom-decomposition-01` | `.benchmark/imported/bom/decomposition/` | `artifacts/bom/decomposition.json` | `decomposition_f1`（确定性 F1；非官方 LLM judge） |
| T2 triage | task2_triage | `lci-triage-01` | `.benchmark/imported/lci/triage/` | `artifacts/triage/triage.json` | `triage_accuracy` |
| T3 mapping | task3_mapping | `lci-mapping-01` | `.benchmark/imported/lci/mapping/` | `artifacts/mapping/mapping.json` | **Top-1** = `exact_match_rate` / `mean_top1` |

01 = 真薄：无 reviewer / 无 skills / 无 node.inject；全局交卷规则仍注入。

## 1. Import（各 30，写 imported，不进 git）

```bash
python3 .benchmark/scripts/import_pcfbench_cases.py \
  --source .eval/data/pcfbench \
  --task task1 --task task2 --task task3 --limit 30
ls -d .benchmark/imported/bom/decomposition/*/ | wc -l   # 30
ls -d .benchmark/imported/lci/triage/*/ | wc -l           # 30
ls -d .benchmark/imported/lci/mapping/*/ | wc -l          # 30
```

jsonl 也可来自 `.cache/benchmark/pcfbench/`（先 `download_pcfbench.py`）。

## 2. Serve tip

须挂含上述 orch 的 tip（≥ `096c294`）。切服后：

```bash
# 例：确认 stem 可见
curl -s http://127.0.0.1:8800/api/workflows | tr ',' '\n' | grep -E 'decomposition-01|triage-01|mapping-01'
```

## 3. 跑 01（DeepSeek profile）

```bash
uv run python .benchmark/scripts/run_batch.py --model <DeepSeek-profile> \
  --workflow bom-decomposition-01 \
  --cases-root .benchmark/imported/bom/decomposition

uv run python .benchmark/scripts/run_batch.py --model <DeepSeek-profile> \
  --workflow lci-triage-01 \
  --cases-root .benchmark/imported/lci/triage

uv run python .benchmark/scripts/run_batch.py --model <DeepSeek-profile> \
  --workflow lci-mapping-01 \
  --cases-root .benchmark/imported/lci/mapping
```

## 4. 打分

```bash
uv run python .benchmark/scripts/score_batch.py --category bom --subcategory decomposition
uv run python .benchmark/scripts/score_batch.py --category lci --subcategory triage
uv run python .benchmark/scripts/score_batch.py --category lci --subcategory mapping
```

结果在 `.benchmark/result/`（gitignore）。

## 以后怎么改

- 换案量：import 改 `--limit` / `--id`
- 换档：加 `*-02/03/04` orch（对照 extract 01–04）
- 换 scorer：`.benchmark/bom|lci/scorers/`；`score_batch.SCORE_SPEC` 登记子类
- T1 若要对齐官方 Gemini judge：另 tip 换 `decomposition_f1`，本文件改主指标说明即可
