# 评测预跑 Runbook（草稿）

本文件**进 git**，用来沉淀「怎么开 serve / 怎么串跑 / 踩过什么坑」，最终收成正式工作脚本。  
单次战役的细账（案 id、日志路径、当次 tip）写在：

`.benchmark/result/_logs/prerun/OPS_NOTES_<模型或战役>.md`（整树默认 gitignore）

当前战役：[`OPS_NOTES_gemma4.md`](result/_logs/prerun/OPS_NOTES_gemma4.md)（Gemma 4 31B IT，2026-10-25）。

## 正式脚本应覆盖的步骤

1. **Serve**：切当前 `origin/master` tip；`merge_serve_credentials`（勿整目录覆盖 `pi-auth`）；短 `PI_RUNTIME_SOCKET`（主仓 `.local/run/pi-v5serve.sock`）。
2. **模型**：`POST /api/models/selection` 或 `run_batch --model <profile_id>`。
3. **矩阵顺序**：`bom-extract`（手写 → imported）→ 收口 → `lci-mapping --include-imported`；abstention 另排。
4. **Gemma Tier1**：`--pace-s 90`（或更长）+ 脚本 429 backoff；禁止 dense 无间隔串跑。
5. **References**：extract 默认自动挂 `input/reference.md`（及来源 PDF 文本别名）；PNNL 等缺源案进 `knowledge_skip`，不烧配额重试。
6. **终态标签**（群口径）：
   - `completed`：节点通过且有产物
   - `transient_hit`：途中 429 / disconnect（可与 completed 并存）
   - `rate_limit`：终态失败且无产物、归因配额
   - `knowledge_skip`：知识源数据问题
7. **产物**：`.benchmark/result/<大类>/<子类>/<case_id>/<run_id>/`；批日志 `.benchmark/result/_logs/`。
8. **评分后置**：先收产物与标签，再 `score_case` / fabrication_rate。

## 入口命令（现行，细节以 OPS 笔记为准）

```bash
uv run python .benchmark/scripts/run_batch.py \
  --model google/gemma-4-31b-it \
  --workflow bom-extract \
  --cases-root .benchmark/imported/bom/extract \
  --pace-s 90 \
  --log-dir .benchmark/result/_logs/prerun

uv run python .benchmark/scripts/run_batch.py \
  --model google/gemma-4-31b-it \
  --workflow lci-mapping \
  --include-imported \
  --pace-s 90 \
  --log-dir .benchmark/result/_logs/prerun
```

## 待办（收成脚本前）

- [ ] mapping 12 案收口数字写入对应 OPS 笔记
- [ ] `run_batch` summary 显式输出 `completed|transient_hit|rate_limit|knowledge_skip`
- [ ] completed+产物 不再把途中 429 当成案间 backoff 的 `rate_limit` 失败
- [ ] abstention 串跑路径与 skip 列表
- [ ] 一键：serve 健康检查 → 选模型 → 按矩阵串跑 → 写 OPS 摘要
