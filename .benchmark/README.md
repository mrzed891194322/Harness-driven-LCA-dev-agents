# `.benchmark`

可复现的 LCA 评测资产。P0 只带合成案例和离线打分：不跑模型，不需要 API key，也不把 PCFBench 的 jsonl / PDF 放进 git。

任意 agent 的入口是 [`.agents/skills/bench-test/SKILL.md`](../.agents/skills/bench-test/SKILL.md)。

## 目录

```
.benchmark/
  bom/
    extract/<id>/      # 抽取案例
    abstention/<id>/   # 拒答案例（paired_case_id 挂抽取）
    harness/           # 本大类 orch / node / spec
    scorers/           # claim_f1、c4、score_case CLI
    schemas/           # 可选
    category.yaml
  lci/
    mapping/<id>/      # 背景数据映射
    harness/           # 预留
    scorers/           # fabrication_rate
    schemas/           # 可选
    category.yaml
  result/              # 真跑产物：大类/子类/case_id/run_id（gitignore；仅 README 进仓）
  imported/            # PCFBench 转化案例树（gitignore；仅 README 进仓）
  manifests/
  scripts/
  schemas/             # 全局共用
  oracle.json          # score-only --self-check
  README.md
```

单案例：`meta.yaml`、`input/`（题面）、`truth/`（真值）、`eval/`（假产物 `artifacts/` + `events.jsonl`）。大类下按**子类**分目录，不再平铺 `cases/`。

真跑答案 / 产物写到 [`result/`](result/README.md)（`.benchmark/result/<大类>/<子类>/<case_id>/<run_id>/`），与案例内 `truth/`、`eval/` 分开；勿与 `.cache/benchmark/`（PCFBench 缓存）混用。整树默认不进 git。

## 外置工作流 / spec

测评 orch / node / spec 放在各大类的 `harness/`（与产品 `harness/` 同构）。YAML 内 `nodes:` / `produces.spec` 写相对仓库根的路径（无短名、无外置优先回退）；API 开跑仍可用 orch 文件 stem。见 [`bom/harness/README.md`](bom/harness/README.md)。产品 `full-lca` 等仍只在 `harness/`。

## 缓存

大文件默认放在 `.cache/benchmark/`（可用环境变量 `BENCHMARK_CACHE` 或 `--cache-root` 覆盖）。允许仓库内 `.cache/` 子树，或仓库外路径；其它仓内路径（如 `.benchmark/`）会被拒绝。路径约定见 [`manifests/cache_layout.yaml`](manifests/cache_layout.yaml)。

```bash
python3 .benchmark/scripts/download_pcfbench.py
# 或：python3 .benchmark/scripts/download_pcfbench.py --cache-root "$BENCHMARK_CACHE"
```

`sha256` 仍为空时文件进 `pcfbench/unverified/`；加上 `--write-sha` 才会把摘要回写到 manifest（这是脚本唯一允许改仓库的地方），并把文件移到 `pcfbench/<sha256>/`。


## 串跑（真跑 API）

需要本机 serve 已起。正式脚本（相对仓根）：

```bash
# 冒烟两案，指定模型与 workflow（2×2 条件），每案 1 次
python3 .benchmark/scripts/run_batch.py \
  --model openai/gpt-4o \
  --workflow bom-extract-03 \
  --repeat 1

# 只跑指定 case、重复 3 次
python3 .benchmark/scripts/run_batch.py \
  --workflow bom-extract-03 --model deepseek/deepseek-chat \
  --case bom-steel-plate --case bom-film-roll --repeat 3
```

日志（含 model / workflow / repeat / case / run_id）与 summary 写在 `.benchmark/result/_logs/`；
单次产物：`.benchmark/result/<大类>/<子类>/<case_id>/<run_id>/`。

## PCFBench → 案例树

```bash
python3 .benchmark/scripts/download_pcfbench.py
# 图1 extract 全量 36（task4+task5 → imported/bom/extract，不进 git）
python3 .benchmark/scripts/import_pcfbench_cases.py --task task4 --task task5
# 子集试用：--limit 5；mapping/triage 另加 --task task3 / task2
python3 .benchmark/scripts/import_pcfbench_cases.py
```

也可用 `--source .eval/data/pcfbench` 或 `--out-root .cache/benchmark/cases`。
详见 [`imported/README.md`](imported/README.md)。

## 许可

[PCFBench](https://huggingface.co/datasets/Watershed-Climate/PCFBench)（`Watershed-Climate/PCFBench`）为 **CC BY-NC-SA 4.0**：非商业、署名、相同方式共享。本仓库只保存文件名、URL 和校验和占位，不保存数据集正文。

`ecoinvent_picklist.jsonl` 不在 Hugging Face 数据集文件列表里，来自配套代码仓库，由公开的 ecoinvent v3.11 Database Overview（Cut-Off AO）筛出。同样只下载到外置缓存。

P0 案例是手写的合成数据。`meta.yaml` 里的 `pcfbench_id` 是虚构指针，用来占住「自建 `case_id`、meta 挂上游 id」的位置，并不是上游行号。

## 大类

| 大类 | 内容 | P0 打分 |
| --- | --- | --- |
| `bom` | `extract/` 抽取 + `abstention/` 拒答（`paired_case_id`） | `claim_f1`、`abstention`、`c4_from_events` |
| `lci` | `mapping/` 合成候选集命中 / 编造 | `fabrication_rate`、`c4_from_events` |

整链 `full-lca` 仍为 P2 预留：还没有案例或打分，不要往本树塞 PCFBench 源文件。

离线入口：

```bash
python3 .benchmark/bom/scorers/score_case.py --mode score-only --self-check
```

## 预跑 Runbook

见 [RUNBOOK.md](RUNBOOK.md)；单次战役笔记在 `result/_logs/prerun/OPS_NOTES_*.md`。
