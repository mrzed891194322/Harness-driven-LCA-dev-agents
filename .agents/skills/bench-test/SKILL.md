---
name: bench-test
description: >-
  评测：fixture 离线打分、API 真跑、以及 run_batch/score_batch 串跑。
  模式：fetch / run / score-only / aggregate / batch。换模时 --model 传 profile_id。
---

# bench-test

给任意 agent 的评测入口。当前四件事：`fetch`（下载到缓存）、`run`（上传资料 → 开跑 → 等完拿产物路径）、`score-only`（读产物或 fixture 打分）、`aggregate`（把分数收成摘要）。

- 默认离线用 `score-only`（不跑模型、不要 API key）。
- 要真跑模型时用 `run`；跑完交出产物路径，再另调 `score-only` / `claim_f1`。**不要**把打分揉进 `run`。

`case_id` 是本仓库自建的。上游 id 只出现在案例 `meta.yaml` 的 `pcfbench_id`。P0 里这些 id 是虚构指针。

## 先选模式

| 模式 | 做什么 | 要不要缓存 / serve |
| --- | --- | --- |
| `score-only` | 用案例 `eval/` 假产物（或 `run` 交出的真实产物）对 `truth/` 打分，stdout JSON | 不要 serve |
| `aggregate` | 同上，stdout 按套件均值；或读已有 `scores.jsonl` | 不要 |
| `fetch` | 只下载 manifest 到缓存（默认 `.cache/benchmark`） | 要缓存；允许 `.cache/` 或仓外 |
| `run` | 经 API 上传参考资料、开 `bom-extract-03`、轮询到结束，交付 `workspace/artifacts/bom/claims.json` | 要 serve（当前 tip） |

许可：PCFBench 是 CC BY-NC-SA 4.0（非商业）。数据集正文不能提交。说明见 [`.benchmark/README.md`](../../../.benchmark/README.md)。

## run

真跑模型、开工作流。本节**只**负责上传 → 开跑 → 盯进度 → 交出产物路径；**不**调用 `claim_f1` / `score-only` / `aggregate`。

### 前置

- serve 已起，且 checkout 是当前 tip（与评测要对齐的 commit）。
- 模型已在面板或 `.local/workflow-agent-models.json` 配好（对**下一趟**开跑生效）。
- API 基址默认 `http://127.0.0.1:7860`（`GUI_PORT`，见 `src/backend/settings.py`）。下文用 `$API`。
- 冒烟默认工作流：`bom-extract-03`（orch 在 `.benchmark/bom/harness/`，API 用 stem；节点/spec 在 YAML 里写仓根相对路径，产物 `.benchmark/bom/harness/specs/bom-claims.yaml` → `bom/claims.json`）。

### 1. 上传参考资料

`POST /api/references`（multipart）。文件落到 `harness/knowledge/inputs/`，进入计划里的参考资料列表。

字段：`files`（可多个）；可选同名数量的 `paths`（覆盖保存名）。

案例输入示例（套件题面）：

```bash
curl -sS -X POST "$API/api/references" \
  -F "files=@.benchmark/bom/extract/bom-steel-plate/input/query.md;filename=query.md"
```

真实 PDF/笔记同理改 `-F files=@...`。成功响应含 `"status":"saved"` 与当前 `files` 列表。开跑用的资料走这里；**分数结果**上传见 [scripts/upload_stub.md](scripts/upload_stub.md)，不是本接口。

### 2. 开跑

`POST /api/workflow/start`，JSON body 对应 `WorkflowStart`（`src/backend/api/app.py`）：

| 字段 | 说明 |
| --- | --- |
| `workflow` | 必填意图；冒烟用 `"bom-extract-03"` |
| `plan` | 计划全文；非空则直接用 |
| `subject` / `functional_unit` / `life_cycle_stages` / `conditions` | `plan` 为空且 `subject` 非空时，服务端用表单字段 + 已上传 references 渲染计划 |

`plan` 与 `subject` 都空会 400（「计划为空」）。已有运行在进行则 409。

```bash
curl -sS -X POST "$API/api/workflow/start" \
  -H 'Content-Type: application/json' \
  -d '{"workflow":"bom-extract-03","subject":"低合金钢板一件","functional_unit":"1 件","life_cycle_stages":"原材料获取","conditions":"见已上传 query.md"}'
```

或直接传 `plan` 全文：`{"workflow":"bom-extract-03","plan":"..."}`。

成功大致为 `{"status":"started","workflow":"bom-extract-03","resume":false}`。**`run_id` 不在 start 响应里**，下一步从 progress/status 读。

### 3. 等待

轮询 `GET /api/workflow/progress`（也可看 `GET /api/workflow/status`）。

```bash
curl -sS "$API/api/workflow/progress"
# 续读：curl -sS "$API/api/workflow/progress?after_seq=$NEXT&run_id=$RUN_ID"
```

关注字段：`run_id`、`status`、`status_reason`、`current_node`、`next_seq`、`items`。

终态（progress 里 `stopped` 会映射成 `interrupted`）：

- `completed` → 成功，记下 `run_id`，进入产物步骤
- `failed` / `interrupted` → 失败；读 `status_reason`，必要时 `GET /api/workflow/events`；**不要假装打分**

建议间隔数秒；`after_seq` 用上次返回的 `next_seq`，并带上本趟 `run_id`（换 run 时响应里 `reset: true`）。

### 4. 产物

成功时交付（相对仓库根）：

`workspace/artifacts/bom/claims.json`

对应 spec：`.benchmark/bom/harness/specs/bom-claims.yaml`（`claim_set`；节点 `bom/claims.json`）。把该路径交给调用方；由调用方再开 `score-only` 或：

```bash
python3 .benchmark/bom/scorers/claim_f1.py \
  .benchmark/bom/extract/<case_id>/truth/claims.json \
  workspace/artifacts/bom/claims.json
```

（上式属于 **score-only**，不是 run 的步骤。）

### 5. 失败

硬故障：progress/status 的 `status_reason`、节点 `error`、`/api/workflow/events`。报告原因与 `run_id` 后停。不要调用打分器，也不要编造 F1。

## score-only

在仓库根目录：

```bash
python3 .benchmark/bom/scorers/score_case.py --mode score-only --self-check
```

`--self-check` 对照 `.benchmark/oracle.json`。退出码 0 且 JSON 里 `self_check.ok` 为 true 才算这批案例仍和打分器一致。

常用参数：

- `--suite bom` / `lci` / `abstention`（可重复；别名 `bom-extract-03`、`mapping`）
- `--case bom-steel-plate`（可重复）
- `--harness`、`--model`：可以传，P0 忽略，原样回显
- `--out-dir /tmp/bench-out`：额外写下 `scores.jsonl`、`summary.json`、`summary.md`、`by_panel/*.csv`

单文件打分（不走套件目录；`run` 产物也可当第二参数）：

```bash
python3 .benchmark/bom/scorers/claim_f1.py \
  .benchmark/bom/extract/bom-steel-plate/truth/claims.json \
  .benchmark/bom/extract/bom-steel-plate/eval/artifacts/claims.json

python3 .benchmark/lci/scorers/fabrication_rate.py \
  .benchmark/lci/mapping/map-low-alloy-steel/truth/mapping.json \
  .benchmark/lci/mapping/map-low-alloy-steel/eval/artifacts/mapping.json

python3 .benchmark/bom/scorers/c4_from_events.py \
  .benchmark/bom/extract/bom-steel-plate/eval/events.jsonl
```

产物对齐：`<大类>/<子类>/<case_id>/{meta.yaml,input/,truth/,eval/}`（如 `bom/extract/`、`bom/abstention/`、`lci/mapping/`）——题面、真值、假运行（`eval/artifacts/` + `events.jsonl`）同树。真跑产物见上一节 `run`。

## aggregate

```bash
python3 .benchmark/bom/scorers/score_case.py --mode aggregate --self-check
python3 .benchmark/bom/scorers/score_case.py --mode aggregate --from-scores /tmp/bench-out/scores.jsonl
```

## fetch

只下载，不打分。缓存根默认 `.cache/benchmark`；也可用 `BENCHMARK_CACHE` 或 `--cache-root`。允许 `.cache/` 子树或仓外；其它仓内路径会退出。

```bash
python3 .benchmark/scripts/download_pcfbench.py --dry-run
python3 .benchmark/bom/scorers/score_case.py --mode fetch --dry-run
# 或显式：--cache-root "$BENCHMARK_CACHE"
```

真下载同一条命令去掉 `--dry-run`。`--write-sha` 会把空的 sha256 写回 `.benchmark/manifests/pcfbench_sources.yaml`。没有这一步就不要把下载结果拷回仓库。校验和仍为空时，文件在 `$BENCHMARK_CACHE/pcfbench/unverified/<文件名>`（未设时即 `.cache/benchmark/...`）。

manifest 列了 task1 / task3 / task4 / task5 / task7 和 `ecoinvent_picklist.jsonl`。picklist 不在 Hugging Face 文件列表里，URL 指向配套仓库。HF 数据集没有单独 PDF；gitignore 仍然拒绝把 PDF 或这些 jsonl 加进来。


## 串跑 batch（多案 × 模型 × workflow）

正式入口（仓内，相对仓根；也可用 `uv run python`）：

```bash
python3 .benchmark/scripts/run_batch.py \
  --model <profile_id> \
  --workflow bom-extract-03 \
  --repeat 1
```

### `--model` 怎么传（易错）

传 **serve 的 profile_id**（`POST /api/models/selection` 的 `profile_id`），**不要**传裸的 `Provider/Model` 展示名。

| 要跑的模型 | `--model` 正确写法 | 错误写法 |
| --- | --- | --- |
| Gemma 4 31B | `google/gemma-4-31b-it` | （同形，此例刚好也是 profile_id） |
| Qwen3.8-27B（SiliconFlow） | `silicon-flow-Qwen-Qwen3.8-27B` | `Qwen/Qwen3.8-27B`（会 400 未知模型） |

查可用 id：

```bash
curl -sS "$API/api/models/profiles" | python3 -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(sorted((d.get('profiles') or {}))))"
```

`$API` 默认 `http://127.0.0.1:8800`（评测 serve；旧文档里的 7860 以当前 `GUI_PORT` / 运维实际端口为准）。

### 常用参数

| 参数 | 含义 | 默认 / 注意 |
| --- | --- | --- |
| `--workflow` | orch stem：`bom-extract-03/04` / `lci-mapping-03/04` / `lci-triage-03/04` | 默认 `bom-extract-03`；abstention **复用** `bom-extract-03/04`，用 `--cases-root .benchmark/bom/abstention` |

档位 **01** 真·薄；**02** 薄编排（无 reviewer，注入同 best）；**03** 薄注入+reviewer；**04** 最好。01/02 orch 未建；本轮图1只跑 extract 03→04。勿再用「02=产品默认 / 03=中间」。

| `--model` | profile_id，见上表 | 必填才换模；会写进日志与 meta |
| `--cases-root` | 案例根（相对仓根） | 按 workflow 映射；手写树或 imported 树 |
| `--include-imported` | 主树 + `.benchmark/imported/<大类>/<子类>/` | 同 id 保留入库树 |
| `--case` | 只跑这些 case_id（可重复） | 默认扫整棵 cases-root |
| `--repeat N` | 每案重复次数 | 默认 1 |
| `--pace-s` | 案间固定间隔秒 | 默认 0；**Gemma4 建议 90**；Qwen 默认不 pace，遇 429 再加 |
| `--max-s` | 单案软告警阈值秒 | 默认 **0=不超时、等到终态**；`>0` 只周期性 WARN，**不结案、不停跑**（防 poll_timeout 幽灵跳案）。案间若仍 running，`wait_idle` 会 stop 再开下一案 |
| `--backoff-base-s` / `--backoff-max-s` | 终态 `rate_limit` 后指数退避 | 默认 60 / 300 |
| `--no-auto-references` | 关掉开跑前自动 POST references | 默认会清 knowledge/inputs 并挂 `input/reference.md`（及 PDF 文本别名） |
| `--log-dir` | 批日志目录 | 默认 `.benchmark/result/_logs` |
| `--api` | serve 根 | 默认 `http://127.0.0.1:8800` |

### 全量矩阵示例（与评测群口径一致）

先归档旧产物，再按类串跑；PNNL 缺 PDF 会 `knowledge_skip`（不必手删）。

```bash
# 0) 归档（勿丢）
mkdir -p .benchmark/result/_archive
mv .benchmark/result/bom .benchmark/result/lci .benchmark/result/_logs .benchmark/result/_scores \
  .benchmark/result/_archive/gemma4-full-<YYYYMMDD>/ 2>/dev/null || true

# 1) 图1 extract 全量 36（imported task4+task5）；03/04 换 stem 即可
python3 .benchmark/scripts/run_batch.py \
  --model google/gemma-4-31b-it \
  --workflow bom-extract-03 \
  --cases-root .benchmark/imported/bom/extract \
  --pace-s 90
# 手写冒烟+imported（2+36）：改用 --include-imported，去掉 --cases-root

# 2) mapping
python3 .benchmark/scripts/run_batch.py \
  --model google/gemma-4-31b-it \
  --workflow lci-mapping-03 \
  --include-imported \
  --pace-s 90

# 3) abstention 手写 2（不扩 imported）
python3 .benchmark/scripts/run_batch.py \
  --model google/gemma-4-31b-it \
  --workflow bom-extract-03 \
  --cases-root .benchmark/bom/abstention \
  --pace-s 90

# Qwen 同矩阵：把 --model 换成 silicon-flow-Qwen-Qwen3.8-27B，默认去掉 --pace-s（或 --pace-s 0）
```

### 产物与 token

- 每案：`.benchmark/result/<大类>/<子类>/<case_id>/<run_id>/`（`meta.json` / `status.json` / `artifacts/`）
- `meta.json` 与批 `summary-*.json` 含 `tokens` / `tokens_total`：`input`、`output`、`cache`（及 `cache_read`/`cache_write`）；provider 没给的字段是字符串 **`unavailable`**，不是静默 0
- 批日志：`.benchmark/result/_logs/batch-<workflow>-<ts>.log` + `summary-<workflow>-<ts>.json`
- 终态标签：`completed` / `transient_hit` / `rate_limit` / `knowledge_skip`（详见 [`.benchmark/RUNBOOK.md`](../../../.benchmark/RUNBOOK.md)）

### 跑完打分

```bash
python3 .benchmark/scripts/score_batch.py
# 可选：--model <profile_id> 只筛该模型产物
```

落盘 `.benchmark/result/_scores/<ts>/`（`summary.json` / `scores.csv` / `scores.md`）。不改 `score_case.py` 案例树路径。

PCFBench 进案例树（不进 git）：

```bash
python3 .benchmark/scripts/import_pcfbench_cases.py --task task4 --task task5   # 图1 全量 36
python3 .benchmark/scripts/import_pcfbench_cases.py --task task4 --limit 5      # 子集
```

见 [`.benchmark/imported/README.md`](../../../.benchmark/imported/README.md)。

## 大类怎么测

| 大类 / 过滤 | 怎么读 |
| --- | --- |
| `bom` | [docs/bom.md](docs/bom.md)（离线 score-only；真跑见上文 `run`） |
| `lci` | [docs/lci.md](docs/lci.md) |
| `abstention` | 同 bom 篇末「拒答」。案例在 `bom/abstention/`，`paired_case_id` 挂抽取案例 |
| `full-lca` | P2 预留，见 [`.benchmark/README.md`](../../../.benchmark/README.md)，不要打分 |

## 指标（P0）

- **claim F1**：有 `value`+`unit` 时先做单位换算（`g`→`kg`，`kWh`→`MJ`，`mass%`→`percent`），四舍五入到 6 位小数，再按元组一一匹配。对不上的预测计为幻觉率。两边都空则 F1 = 1。
- **编造率**：预测的 `process_id` / `process_name` 不在 expected 的 `candidates` 里。模型自己写在交付物里的 `candidates` 不算数。`exact_match_rate` 另对 `options` 报告。
- **拒答**：`claims` 非空就算没有拒答。`abstention_correct` 要求真值要拒答且预测确实是空列表。
- **C4**：数 `events.jsonl` 里的 reject / redo。`redo_*`、`submit_rejected`、`route.when` 为 `reject` 或 `checks_failed`、`submit.verdict=reject`。单独的 `host_checks` 不计。`c4_if = reject_count + redo_count`。

## 上传说明

- **开跑资料**：`POST /api/references`，步骤在 `run`。
- **分数结果**：P0 仍无结果接口；占位说明 [scripts/upload_stub.md](scripts/upload_stub.md)。不要把分数 POST 到 `/api/references` 或 `/api/workflow/*`。
