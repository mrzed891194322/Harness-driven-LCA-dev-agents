# 评测预跑 Runbook（草稿）

本文件**进 git**，用来沉淀「怎么开 serve / 怎么串跑 / 踩过什么坑」，最终收成正式工作脚本。  
单次战役按六格累加（gitignore）：

- `result/_logs/prerun/RUNBOOK-<model>.md`（定字段：meta/cmd/env/counts/incidents/next）
- `result/_logs/prerun/OPS_NOTES_*.md`（运维细账，可选）

当前：`RUNBOOK-gemma4.md`、`OPS_NOTES_gemma4.md`。

## 正式脚本应覆盖的步骤

1. **Serve**：切当前 `origin/master` tip；`merge_serve_credentials`（勿整目录覆盖 `pi-auth`）；短 `PI_RUNTIME_SOCKET`（主仓 `.local/run/pi-v5serve.sock`）。
2. **模型**：`POST /api/models/selection` 或 `run_batch --model <profile_id>`。
   - **必须传 profile_id**（如 `google/gemma-4-31b-it`、`silicon-flow-Qwen-Qwen3.8-27B`），不要传展示用的 `Qwen/Qwen3.8-27B`（会 400）。
   - 列表：`GET /api/models/profiles` → `profiles` 的 key。
   - 详参与全量矩阵示例见 `.agents/skills/bench-test/SKILL.md`「串跑 batch」。
3. **矩阵顺序**：`bom-extract`（手写 → imported）→ 收口 → `lci-mapping --include-imported`；abstention 另排。
4. **限速（按模型档，非全局）**：仅 Gemma4 及同类强限速才开 `--pace-s` / 429 backoff；其它模型默认 `--pace-s 0`。细节见战役笔记 `result/_logs/prerun/RUNBOOK-gemma4.md`。
5. **References**：extract 默认自动挂 `input/reference.md`（及来源 PDF 文本别名）；PNNL 等缺源案进 `knowledge_skip`，不烧配额重试。
6. **终态标签**（群口径）：
   - `completed`：节点通过且有产物
   - `transient_hit`：途中 429 / disconnect（可与 completed 并存）
   - `rate_limit`：终态失败且无产物、归因配额
   - `knowledge_skip`：知识源数据问题
7. **产物**：`.benchmark/result/<大类>/<子类>/<case_id>/<run_id>/`；批日志 `.benchmark/result/_logs/`。
8. **评分后置**：先收产物与标签，再扫 result 树打分：
   `uv run python .benchmark/scripts/score_batch.py --model <profile_id>`
   （落 `result/_scores/<ts>/`：summary.json + scores.csv + scores.md；
   复用 claim_f1 / fabrication_rate；不改 `score_case.py` 案例树路径）。

## 入口命令

通用（默认无限速）：

```bash
uv run python .benchmark/scripts/run_batch.py \
  --model <profile_id> \
  --workflow bom-extract \
  --cases-root .benchmark/imported/bom/extract \
  --log-dir .benchmark/result/_logs/prerun
```

Gemma4 档另加 `--pace-s 90`。`--max-s` 默认 0（不硬超时；真卡靠例行介入）。案间残留 running 时 `run_batch` 会 stop 再开。（及脚本内 429 backoff）；战役六格笔记见 `result/_logs/prerun/RUNBOOK-gemma4.md` / `OPS_NOTES_gemma4.md`。

## 待办（收成脚本前）

- [ ] mapping 12 案收口数字写入对应 OPS 笔记
- [x] `run_batch` summary 显式输出 `completed|transient_hit|rate_limit|knowledge_skip`
- [x] completed+产物 不再把途中 429 当成案间 backoff 的 `rate_limit` 失败
- [ ] abstention 串跑路径与 skip 列表
- [ ] 一键：serve 健康检查 → 选模型 → 按矩阵串跑 → 写 OPS 摘要
