# `.benchmark/result/`

评测**真跑**写出的答案 / 产物落点（与案例树内的 `truth/`、`eval/` 分开）。

## 路径

```
.benchmark/result/
  <大类>/<子类>/<case_id>/<run_id>/
```

例：

```
.benchmark/result/bom/extract/bom-steel-plate/<run_id>/
.benchmark/result/bom/abstention/abstain-steel-plate-nodoc/<run_id>/
.benchmark/result/lci/mapping/map-low-alloy-steel/<run_id>/
```

离线打分汇总也可写到同树（如 `--out-dir .benchmark/result/...`），勿塞进各大类案例目录。

## 与缓存区分

| 路径 | 用途 |
| --- | --- |
| `.benchmark/result/` | 本仓评测跑出的答案 / 产物（本目录） |
| `.cache/benchmark/` | PCFBench 等上游大文件缓存（`BENCHMARK_CACHE` / `--cache-root`） |

两者不要混用。整树默认不进 git（见仓根 `.gitignore`）；仅本 README 受版本管理。
