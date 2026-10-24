# `.benchmark`

可复现的 LCA 评测资产。P0 只带合成 fixture 和离线打分：不跑模型，不需要 API key，也不把 PCFBench 的 jsonl / PDF 放进 git。

任意 agent 的入口是 [`.agents/skills/bench-test/SKILL.md`](../.agents/skills/bench-test/SKILL.md)。

## 缓存

大文件默认放在 `.cache/benchmark/`（可用环境变量 `BENCHMARK_CACHE` 或 `--cache-root` 覆盖）。允许仓库内 `.cache/` 子树，或仓库外路径；其它仓内路径（如 `.benchmark/`）会被拒绝。路径约定见 [`manifests/cache_layout.yaml`](manifests/cache_layout.yaml)。

```bash
python3 .benchmark/scripts/download_pcfbench.py
# 或：python3 .benchmark/scripts/download_pcfbench.py --cache-root "$BENCHMARK_CACHE"
```

`sha256` 仍为空时文件进 `pcfbench/unverified/`；加上 `--write-sha` 才会把摘要回写到 manifest（这是脚本唯一允许改仓库的地方），并把文件移到 `pcfbench/<sha256>/`。

## 许可

[PCFBench](https://huggingface.co/datasets/Watershed-Climate/PCFBench)（`Watershed-Climate/PCFBench`）为 **CC BY-NC-SA 4.0**：非商业、署名、相同方式共享。本仓库只保存文件名、URL 和校验和占位，不保存数据集正文。

`ecoinvent_picklist.jsonl` 不在 Hugging Face 数据集文件列表里，来自配套代码仓库，由公开的 ecoinvent v3.11 Database Overview（Cut-Off AO）筛出。同样只下载到外置缓存。

P0 案例是手写的合成数据。`meta.yaml` 里的 `pcfbench_id` 是虚构指针，用来占住「自建 `case_id`、meta 挂上游 id」的位置，并不是上游行号。

## 套件

| 套件 | 内容 | P0 打分 |
| --- | --- | --- |
| `bom-extract` | 合成物料/能耗声明，对应日后的 task4 + task5 | `claim_f1`、`c4_from_events` |
| `mapping` | 合成候选集命中 / 编造，对应日后的 task3 | `fabrication_rate`、`c4_from_events` |
| `abstention` | 与 BOM 案例配对，但输入没有来源文档 | 拒答是否成立、`claim_f1`、`c4_from_events` |
| `full-lca` | 空壳，见该目录 README | 还没有 |

案例真值在 `suites/<suite>/cases/<case_id>/`。模型侧假产物和 `events.jsonl` 在 `fixtures/<suite>/<case_id>/`。两边用自建 `case_id` 对齐。
