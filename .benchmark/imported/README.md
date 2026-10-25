# `.benchmark/imported/`

由 [`.benchmark/scripts/import_pcfbench_cases.py`](../scripts/import_pcfbench_cases.py) 从 PCFBench 缓存转化出的**全量/子集案例树**。

```
.benchmark/imported/
  bom/extract/<case_id>/
  lci/mapping/<case_id>/
```

- **整树默认不进 git**（仓根 `.gitignore`）；仅本 README 受版本管理。
- 含 `input/reference.md`（document_text）等大文件时体积大，勿手工 `git add`。
- 精选冒烟仍放在已入库的 `.benchmark/bom|lci/...`（合成或经审的子集）。
- 上游 dump 本身仍在 `.cache/benchmark/pcfbench/`（见 `download_pcfbench.py`）。

```bash
python3 .benchmark/scripts/download_pcfbench.py
python3 .benchmark/scripts/import_pcfbench_cases.py --task task4 --limit 5
# 或指向已有 jsonl：
python3 .benchmark/scripts/import_pcfbench_cases.py --source .eval/data/pcfbench --task task4 --id bd4b589933ef4d7e79c207f4
```
