# `.benchmark/imported/`

由 [`.benchmark/scripts/import_pcfbench_cases.py`](../scripts/import_pcfbench_cases.py) 从 PCFBench 缓存转化出的**全量/子集案例树**。

```
.benchmark/imported/
  bom/extract/<case_id>/     # 图1 全量：task4+task5 = 36（不进 git）
  bom/decomposition/<case_id>/  # task1 组成（按需 import；DeepSeek 01×30）
  lci/mapping/<case_id>/
  lci/triage/<case_id>/      # task2（按需 import）
```

- **整树默认不进 git**（仓根 `.gitignore`）；仅本 README 受版本管理。
- 含 `input/reference.md`（document_text）等大文件时体积大，勿手工 `git add`。
- 精选冒烟仍放在已入库的 `.benchmark/bom|lci/...`（合成或经审的子集；extract 冒烟 2 案，**不计入**图 1 的 36）。
- 上游 dump 本身仍在 `.cache/benchmark/pcfbench/` 或 `.eval/data/pcfbench/`（见 `download_pcfbench.py`）。

## 图1 extract 全量（36）

```bash
# 写入/刷新 imported extract（task4=22 + task5=14）
python3 .benchmark/scripts/import_pcfbench_cases.py --task task4 --task task5
# 校验
ls -d .benchmark/imported/bom/extract/*/ | wc -l   # 期望 36
```

子集试用可加 `--limit 5` 或 `--id <pcfbench_id>`。

## 挂到可跑树（串跑）

入库冒烟仍在 `.benchmark/bom|lci/...`；imported 默认**不**复制进那两棵树。

```bash
# 图1 全量 extract（仅 36 条 PCFBench）
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow bom-extract-03 \
  --cases-root .benchmark/imported/bom/extract

# 最好档同树
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow bom-extract-04 \
  --cases-root .benchmark/imported/bom/extract

# 冒烟手写 + imported 合并（同 id 保留入库；会变成 2+36）
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow bom-extract-03 --include-imported

# mapping / triage（图2/3 数量本轮不变）
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow lci-mapping-03 --include-imported

# abstention：复用 bom-extract-03/04 orch，换案例根（PCFBench 无独立拒答 task）
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow bom-extract-03 --cases-root .benchmark/bom/abstention
```

## DeepSeek 01 × Task1/2/3（各 30）

```bash
python3 .benchmark/scripts/import_pcfbench_cases.py --source .eval/data/pcfbench \
  --task task1 --task task2 --task task3 --limit 30
# 期望各 30：
ls -d .benchmark/imported/bom/decomposition/*/ | wc -l
ls -d .benchmark/imported/lci/triage/*/ | wc -l
ls -d .benchmark/imported/lci/mapping/*/ | wc -l

# 跑批（serve 须挂含 *-01 的 tip；--cases-root 指 imported）
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow bom-decomposition-01 --cases-root .benchmark/imported/bom/decomposition
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow lci-triage-01 --cases-root .benchmark/imported/lci/triage
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow lci-mapping-01 --cases-root .benchmark/imported/lci/mapping

# 打分（T1=decomposition F1；T2=accuracy；T3 主报 mean_top1=exact_match_rate）
uv run python .benchmark/scripts/score_batch.py --category bom --subcategory decomposition
uv run python .benchmark/scripts/score_batch.py --category lci --subcategory triage
uv run python .benchmark/scripts/score_batch.py --category lci --subcategory mapping
```

T1 scorer 为确定性成分集合 F1（`decomposition_f1.py`），notes 标明非官方 LLM judge。

