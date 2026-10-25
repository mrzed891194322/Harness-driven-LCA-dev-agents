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

## 挂到可跑树（串跑）

入库冒烟仍在 `.benchmark/bom|lci/...`；imported 默认**不**复制进那两棵树。

串跑挂法（任选）：

```bash
# 只跑 imported extract
python3 .benchmark/scripts/run_batch.py --model google/gemma-4-31b-it \
  --workflow bom-extract --cases-root .benchmark/imported/bom/extract

# 入库 + imported 合并（同 id 保留入库）
python3 .benchmark/scripts/run_batch.py --model google/gemma-4-31b-it \
  --workflow bom-extract --include-imported

# mapping 薄档 orch（需 serve tip 含 lci-mapping）
python3 .benchmark/scripts/run_batch.py --model google/gemma-4-31b-it \
  --workflow lci-mapping --include-imported

# abstention：复用 bom-extract orch，换案例根（PCFBench 无独立拒答 task，目前只有手写 2 案）
python3 .benchmark/scripts/run_batch.py --model google/gemma-4-31b-it \
  --workflow bom-extract --cases-root .benchmark/bom/abstention
```

`run_batch` 默认开跑前会清空并 `POST /api/references`（`reference.md` + 来源 PDF 文本别名）；`--no-auto-references` 可关。abstention 仍无 PCFBench import 源。
