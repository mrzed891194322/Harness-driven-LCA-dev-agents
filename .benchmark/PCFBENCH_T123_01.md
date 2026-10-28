**权威总规范**：[docs/PCFBENCH_EVAL_HOWTO.md](docs/PCFBENCH_EVAL_HOWTO.md)。

# PCFBench T2/T3 · 01 真薄（本轮可验跑）

**本轮范围（Du Yuan 2026-10-28）：只落 T2 triage + T3 mapping。**  
T1 decomposition **搁置**（官方要 LLM judge，确定性 F1 骨架可留着，本轮不跑、不验）。  
目标：**机制完整优先于准度**——import → `*-01` orch → submit → scorer → `run_batch`/`score_batch`。

| 任务 | 官方 | stem | cases-root | 产物 | 主指标 |
|------|------|------|------------|------|--------|
| T2 triage | task2_triage | `lci-triage-01` | `.benchmark/imported/lci/triage/` | `artifacts/triage/triage.json` | `triage_accuracy` |
| T3 mapping | task3_mapping | `lci-mapping-01` | `.benchmark/imported/lci/mapping/` | `artifacts/mapping/mapping.json` | **Top-1** = `exact_match_rate` / `mean_top1` |
| ~~T1 组成~~ | task1_decomposition | `bom-decomposition-01` | `.benchmark/imported/bom/decomposition/` | — | **本轮不做** |

01 = 真薄（对齐 `bom-extract-01`）：无 reviewer / 无 skills / 无 node.inject；全局交卷规则仍注入。
02 = 同拓扑 + `bom-claims-slim` 薄约束（压多报/单位硬伤）；仍无 reviewer。
03 = 02 之上加 reviewer（`bom-claims-review`：读长文；删无支持；单位照抄；慎补漏）；executor 仍 slim。

### 计划 / 知识接线（Du Yuan 2026-10-28 硬口径：原版题面 + 原件）

- **计划**：`run_batch` YAML `items` 一项；`title` = PCFBench 英文任务名；`content` = `query.md` **题面-only**（T2/T3 = 官方英文 user prompt，禁自拟中文壳）。
- **extract**：挂 `input/reference.md` = `document_text` → `knowledge`；`source_url` 仅 meta；PDF cache 可选核对、非评测输入。
- **T2/T3**：挂 `pcfbench_input.json`（及 mapping `options.json`）→ `bom`（官方原输入）。详见 [docs/PCFBENCH_EVAL_HOWTO.md](docs/PCFBENCH_EVAL_HOWTO.md)。


## 1. Import（seed=20261028 抽 30，写 imported，不进 git）

全量 jsonl 在 `.eval/data/pcfbench/`（或 `.cache/benchmark/pcfbench/`，先 `download_pcfbench.py`）。  
`--seed` + `--limit`：对候选行 `Random(seed).sample`；无 seed 则取前 N 条。

```bash
# 重抽前可清（gitignore，安全）
rm -rf .benchmark/imported/lci/triage .benchmark/imported/lci/mapping

python3 .benchmark/scripts/import_pcfbench_cases.py \
  --source .eval/data/pcfbench \
  --task task2 --task task3 \
  --limit 30 --seed 20261028

ls -d .benchmark/imported/lci/triage/*/ | wc -l    # 30
ls -d .benchmark/imported/lci/mapping/*/ | wc -l   # 30
```

## 2. Serve tip

验跑 tip 须含 `lci-triage-01` / `lci-mapping-01`（主仓 tip，见群消息）。  
**Extract DeepSeek 窗口内可不切服**（serve 可仍挂旧 tip）；空窗再 checkout 本 tip 后重启 serve。

```bash
curl -s http://127.0.0.1:8800/api/workflows | tr ',' '\n' | grep -E 'triage-01|mapping-01'
```

## 3. 跑 01（DeepSeek profile）各 30

```bash
uv run python .benchmark/scripts/run_batch.py --model <DeepSeek-profile> \
  --workflow lci-triage-01 \
  --cases-root .benchmark/imported/lci/triage

uv run python .benchmark/scripts/run_batch.py --model <DeepSeek-profile> \
  --workflow lci-mapping-01 \
  --cases-root .benchmark/imported/lci/mapping
```

## 4. 打分

```bash
uv run python .benchmark/scripts/score_batch.py --category lci --subcategory triage
uv run python .benchmark/scripts/score_batch.py --category lci --subcategory mapping
# T3 看汇总里的 mean_top1（= mean_exact_match_rate）
```

结果在 `.benchmark/result/`（gitignore）。

## 路径表

| 项 | 路径 |
|----|------|
| orch | `.benchmark/lci/harness/workflows/orchestrations/lci-{triage,mapping}-01.yaml` |
| node | `.benchmark/lci/harness/workflows/nodes/lci-{triage,mapping}-01.yaml` |
| spec | `.benchmark/lci/harness/specs/lci-{triage,mapping}-01.yaml` |
| scorer | triage → `.benchmark/lci/scorers/triage_accuracy.py`；mapping Top-1 → `fabrication_rate.exact_match_rate` |
| import | `.benchmark/scripts/import_pcfbench_cases.py` |
| 案池 | `.benchmark/imported/lci/{triage,mapping}/` |

## 以后怎么改

- 换案量 / 可复现抽样子集：改 `--limit` / `--seed` / `--id`
- 换档：加 `*-02/03/04` orch（对照 extract 01–04）
- 换 scorer：`.benchmark/lci/scorers/` + `score_batch.SCORE_SPEC`
- T1 恢复：官方 LLM judge 另 tip；现有 `bom-decomposition-01` + `decomposition_f1` 仅骨架
