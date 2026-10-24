---
name: bench_test
description: >-
  用仓库里的合成 fixture 给 LCA 原子步离线打分。用户要跑 bench、score-only、
  汇总分数，或只把 PCFBench 下载到缓存（默认 .cache/benchmark）时使用。
---

# bench_test

给任意 agent 的评测入口。P0 只做三件事：`fetch`（下载到缓存）、`score-only`（读 fixture 打分）、`aggregate`（把分数收成摘要）。不跑模型，不需要 API key，不连接 MCP，也不要改 harness。

`case_id` 是本仓库自建的。上游 id 只出现在案例 `meta.yaml` 的 `pcfbench_id`。P0 里这些 id 是虚构指针。

## 先选模式

| 模式 | 做什么 | 要不要缓存 |
| --- | --- | --- |
| `score-only` | 用 `fixtures/` 里的假产物对 `suites/` 的 expected 打分，stdout 打 JSON | 不要 |
| `aggregate` | 同上，但 stdout 是按套件的均值；或读已有 `scores.jsonl` | 不要 |
| `fetch` | 只下载 manifest 里的文件到缓存（默认 `.cache/benchmark`） | 要；允许 `.cache/` 或仓外 |

没有 `run`。不要默认去调宿主编排或模型。

许可：PCFBench 是 CC BY-NC-SA 4.0（非商业）。数据集正文不能提交。说明见 [`.benchmark/README.md`](../../../.benchmark/README.md)。

## score-only

在仓库根目录：

```bash
python3 .benchmark/scorers/score_case.py --mode score-only --self-check
```

`--self-check` 对照 `.benchmark/fixtures/oracle.json`。退出码 0 且 JSON 里 `self_check.ok` 为 true 才算这批 fixture 仍和打分器一致。

常用参数：

- `--suite bom-extract`（可重复）
- `--case bom-steel-plate`（可重复）
- `--harness`、`--model`：可以传，P0 忽略，原样回显
- `--out-dir /tmp/bench-out`：额外写下 `scores.jsonl`、`summary.json`、`summary.md`、`by_panel/*.csv`

单文件打分（不走套件目录）：

```bash
python3 .benchmark/scorers/claim_f1.py \
  .benchmark/suites/bom-extract/cases/bom-steel-plate/expected/claims.json \
  .benchmark/fixtures/bom-extract/bom-steel-plate/artifacts/claims.json

python3 .benchmark/scorers/fabrication_rate.py \
  .benchmark/suites/mapping/cases/map-low-alloy-steel/expected/mapping.json \
  .benchmark/fixtures/mapping/map-low-alloy-steel/artifacts/mapping.json

python3 .benchmark/scorers/c4_from_events.py \
  .benchmark/fixtures/bom-extract/bom-steel-plate/events.jsonl
```

产物对齐：`suites/<suite>/cases/<case_id>/{input,expected,meta.yaml}` 是题面和真值；`fixtures/<suite>/<case_id>/artifacts/` 加 `events.jsonl` 是待打分的假运行。

## aggregate

```bash
python3 .benchmark/scorers/score_case.py --mode aggregate --self-check
python3 .benchmark/scorers/score_case.py --mode aggregate --from-scores /tmp/bench-out/scores.jsonl
```

## fetch

只下载，不打分。缓存根默认 `.cache/benchmark`；也可用 `BENCHMARK_CACHE` 或 `--cache-root`。允许 `.cache/` 子树或仓外；其它仓内路径会退出。

```bash
python3 .benchmark/scripts/download_pcfbench.py --dry-run
python3 .benchmark/scorers/score_case.py --mode fetch --dry-run
# 或显式：--cache-root "$BENCHMARK_CACHE"
```

真下载同一条命令去掉 `--dry-run`。`--write-sha` 会把空的 sha256 写回 `.benchmark/manifests/pcfbench_sources.yaml`。没有这一步就不要把下载结果拷回仓库。校验和仍为空时，文件在 `$BENCHMARK_CACHE/pcfbench/unverified/<文件名>`（未设时即 `.cache/benchmark/...`）。

manifest 列了 task1 / task3 / task4 / task5 / task7 和 `ecoinvent_picklist.jsonl`。picklist 不在 Hugging Face 文件列表里，URL 指向配套仓库。HF 数据集没有单独 PDF；gitignore 仍然拒绝把 PDF 或这些 jsonl 加进来。

## 套件怎么测

| 套件 | 怎么读 |
| --- | --- |
| `bom-extract` | [docs/bom-extract.md](docs/bom-extract.md) |
| `mapping` | [docs/mapping.md](docs/mapping.md) |
| `abstention` | 同上篇末「拒答」。案例用 `paired_case_id` 指向 BOM 案例，输入里没有文档 |
| `full-lca` | 只有 [`.benchmark/suites/full-lca/README.md`](../../../.benchmark/suites/full-lca/README.md)，不要打分 |

## 指标（P0）

- **claim F1**：有 `value`+`unit` 时先做单位换算（`g`→`kg`，`kWh`→`MJ`，`mass%`→`percent`），四舍五入到 6 位小数，再按元组一一匹配。对不上的预测计为幻觉率。两边都空则 F1 = 1。
- **编造率**：预测的 `process_id` / `process_name` 不在 expected 的 `candidates` 里。模型自己写在交付物里的 `candidates` 不算数。`exact_match_rate` 另对 `options` 报告。
- **拒答**：`claims` 非空就算没有拒答。`abstention_correct` 要求真值要拒答且预测确实是空列表。
- **C4**：数 `events.jsonl` 里的 reject / redo。`redo_*`、`submit_rejected`、`route.when` 为 `reject` 或 `checks_failed`、`submit.verdict=reject`。单独的 `host_checks` 不计。`c4_if = reject_count + redo_count`。

## 上传脚本

P0 没有前后端上传实现。说明在 [scripts/upload_stub.md](scripts/upload_stub.md)。不要编一个真实的上传 URL 去 POST。
