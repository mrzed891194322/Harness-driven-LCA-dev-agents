# 本系统如何跑 PCFBench / 评测（规范）

> **权威口径**（Du Yuan 2026-10-28）。设计与改工作流以本文为准；改 `run_batch` / import / 01 接线须**同步改本文**。  
> 任务子集与抽案细节另见 [`../PCFBENCH_T123_01.md`](../PCFBENCH_T123_01.md)、[`../RUNBOOK.md`](../RUNBOOK.md)。

## 1. 计划（全任务 01）

**禁止**把 `query.md` 原文当作 `/api/workflow/start` 的裸 `plan` 字符串糊进去。

须发合法 YAML items（由 `run_batch.build_plan_start_body` 构造）：

```yaml
kind: lca_execution_plan
version: 2
template_id: bom-only   # 或 lca-only；extract/decomp 默认 bom-only，lci-* 默认 lca-only
items:
  - title: Material/energy extraction   # PCFBench 英文任务名；禁自拟中文壳
    content: |                          # = 本案 input/query.md（题面-only）
      …
```

**`query.md` 题面-only（T1/T2/T3/T4/T5 同口径）**：只留 PCFBench **原版提示词**，禁止 `# {case_id}`、来源脚注、自拟中文「任务/交卷」壳。

| 任务 | `query.md` 内容 |
|------|-----------------|
| **T4/T5 extract** | `input.query` 英文题原文；`source_url` 只在 `meta.yaml`（非附件）；知识另挂 `document_text`→`reference.md` |
| **T2 triage** | 官方 user prompt：`MARKET` + `ROOT MATERIAL CONTEXT` 块 |
| **T3 mapping** | 官方 user prompt：`Material` / `Description` / … + `Ecoinvent reference products`（`expected.options`） |
| **T1 decomposition** | 官方 user prompt：`Product` / `Description` / `Functional unit` + `List the BOM components.` |

计划 `items[].content` = 该题面全文；`items[].title` 用上表英文任务名（见 `PLAN_ITEM_TITLE`）。

等价 JSON 请求体：

```json
{
  "workflow": "bom-extract-01",
  "plan": "",
  "template_id": "bom-only",
  "items": [{"title": "Material/energy extraction", "content": "<query.md 题面-only>"}]
}
```

适用：`bom-extract-01`、`bom-decomposition-01`、`lci-triage-01`、`lci-mapping-01`（及同族 01）。

## 2. 上传（references）

### 官方给法（extract / T2 / T3）

| 题 | plan（`query.md`） | 给 agent 的知识/附件 | 不作评测输入 |
|----|-------------------|----------------------|--------------|
| **extract** | `input.query` only | `document_text` → `reference.md`（knowledge） | `source_url` 元数据；PDF cache 可选核对 |
| **T2 triage** | 官方 MARKET + ROOT CONTEXT | `pcfbench_input.json`（原 `input`） | — |
| **T3 mapping** | 官方 Material/… + options 列表 | `pcfbench_input.json` + `options.json` | — |

上传走 `POST /api/references`，`types` 与文件一一对应。`run_batch.stage_case_references` 实现下列规则。

| 任务 | 规则 |
|------|------|
| **T4/T5 extract** | **官方给法**：挂 `input/reference.md` = jsonl `document_text`（纯文本），`type=knowledge`。`source_url` 仅 meta，**不当附件**。PDF（`--source-pdfs`→`.cache/.../source_pdfs/`）可选人工核对，**非评测输入**。缺 `document_text`/`reference.md` → 失败清单。 |
| **T2 triage** | **官方给法**：plan=官方 MARKET+CONTEXT 题面；挂原件 `pcfbench_input.json`（jsonl `input`），`type=bom`。勿 PDF 替代。 |
| **T3 mapping** | **官方给法**：plan=官方 Material/… 题面；挂 `pcfbench_input.json` + `options.json`，`type=bom`。勿 PDF 替代。 |
| **T1 decomposition** | plan=官方 Product/… 题面；挂 `pcfbench_input.json`，`type=bom`。 |

开跑前会清空已有 references，再按上表挂本案文件。

## 3. 01 / 02 / 03 extract 档怎么跑

01 = 真薄：无 reviewer / 无 skills / 无 node.inject；全局交卷规则仍由宿主注入。  
**01→02**：同拓扑、同给法（官方 query + `reference.md`）；02 挂 `bom-claims-flow` + executor `rules: [rules/delivery/read-skills-first.yaml]`（先读已挂技能；抬到达率；**node.inject 仍空**）。技能：轻自检、禁弃权空交；黑名单仅 h/°C；单位短符号+硬反例；短防多报（`refs/`）。旧 `bom-claims-slim` 已弃用。**produce 与 01 同绑**共享 `bom-claims.yaml`。`bom-claims-unit-phrase.yaml` 已废弃（`f4ff815`）。**验收（操作员）**：技能读取率≥90%；NV×02 `--repeat 2` 均值≥0.54；对照 `…144453` / `…201457`。  
**02→03**：给法不变；**专用** `.benchmark/.../agents/bom-extract-{executor,reviewer}.yaml` 薄提示词编排；**本档不挂技能**（不靠厚技能抬分，04 再挂）。对照基线 TAG `…extract03-…015220` / `…extract02-…003412`；钉 tip **先不开批**。  
**04**：厚注入（read+ops）+ reviewer（另档）。

| stem | cases-root（全量/抽样子集） | 主产物 | 主指标 |
|------|------------------------------|--------|--------|
| `bom-extract-01` | `.benchmark/imported/bom/extract/` | `artifacts/bom/claims.json` | Claim F1 |
| `bom-extract-02` | 同 01 | 同 01 | Claim F1 |
| `bom-extract-03` | 同 01 | 同 01 | Claim F1 |
| `lci-triage-01` | `.benchmark/imported/lci/triage/` | `artifacts/triage/triage.json` | `triage_accuracy` |
| `lci-mapping-01` | `.benchmark/imported/lci/mapping/` | `artifacts/mapping/mapping.json` | **Top-1** = `mean_top1` |

```bash
# 例：extract 01（英伟达 profile_id 替换 <profile>）
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow bom-extract-01 \
  --cases-root .benchmark/imported/bom/extract

# 02：同案池，仅 bom-claims-flow
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow bom-extract-02 \
  --cases-root .benchmark/imported/bom/extract

# 03：专用 agent 编排、无技能（先 tip，开批另令）
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow bom-extract-03 \
  --cases-root .benchmark/imported/bom/extract

uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow lci-triage-01 \
  --cases-root .benchmark/imported/lci/triage

uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow lci-mapping-01 \
  --cases-root .benchmark/imported/lci/mapping

# 打分
uv run python .benchmark/scripts/score_batch.py --category bom --subcategory extract
uv run python .benchmark/scripts/score_batch.py --category lci --subcategory triage
uv run python .benchmark/scripts/score_batch.py --category lci --subcategory mapping
```

Import / 抽 30：`import_pcfbench_cases.py --task … --limit 30 --seed 20261028`（见 T123 文档）。案池默认 `.benchmark/imported/`（gitignore）。

extract 知识来自 jsonl `document_text`（import→`reference.md`）。可选 PDF 缓存核对：`download_pcfbench.py --source-pdfs`（失败见 `.cache/.../source_pdfs/failures.jsonl`）；**PDF 非评测输入**。

## 4. 打分口径（相对 PCFBench 原版）

权威原版字段见 `.eval/data/pcfbench/README.md`。**原版没有的答案字段不得当打分事项**（可留内部/交付字段）。

| 任务 | 原版 expected | 原版主指标 | 我们 scorer 比什么 | 我们多写了什么（内部可留） | 不得当打分钥匙 |
|------|---------------|------------|-------------------|------------------------------|----------------|
| T2 triage | `should_map: bool` | Accuracy / F₁ | 只比 `should_map`（`triage_accuracy`） | gold `candidate_name`；pred `rationale`/`confidence`（ECE 仅旁路） | `candidate_name` / `rationale` 不对则不算错 |
| T3 mapping | `options[]`、`banned_substring`、relevant_* | **Exact-match top-1**（过程名 ∈ options） | `process_name`（或 provider/flow 名）对 `options` → `exact_match_rate` / `mean_top1`；旁路 candidate_hit / banned | gold `items[].item_id`（默认 `m1`）、`candidates[]`、`material_name`；pred 其它 schema 字段 | **`item_id`（含 ≠`m1`）禁止记 abstained/扣分**；单条按位/过程名对齐 |
| T4/T5 extract | `claims[{value,unit,evidence}]` | Claim F1（value, unit） | 只比规范化 `(value, unit)`（`claim_f1`） | `claim_id` / `item_id` / `field` / `text` / `abstained`；evidence 原版有但不参与匹配 | `claim_id` / `item_id` / `field` / `evidence` / `text` 不参与 F1 |

对齐规则（mapping）：**单 gold +（单 pred 或仅一条有过程名）→ 按位对齐比过程名**；多条仍按 `item_id`。headline 用 `mean_top1`，勿把 claim 系 `no_artifact` 叙事套到已有 mapping 产物上。

`run_batch` notes：`lci-mapping` / `lci-triage` **不跑 claim_f1**，缺 `claims.json` 属正常；notes 只写本任务 metric（mapping→`top1`/`hit`；triage→`acc`）。有产物时禁止再写 `F1=…(no_artifact)`。


## 5. serve / tip 要点（**单根主仓**）

- 评测 **serve 与 run_batch 都钉 tip-of-master 主仓**：`PROJECT_ROOT/workspace`。**不要**长期两套根；分支短命合进 master。
- 切 tip = 主仓空窗 `git pull` / `checkout` 目标 tip 后重启 8800/3000（勿靠长期 `.local/wt/serve` 旁路）。
- `.local/wt/serve/...` 若仍在盘上，只作可选短命开发；**批跑默认不得选中**其 `workspace/`。
- 验 01 接线至少含：`build_plan_start_body` + 无别名的 `stage_case_references`（见 tip 说明）。
- 本轮先做 **01**，不追 02–04 厚档。
- 缺 `reference.md`（`document_text`）的 extract 案：staging 失败；须重导补知识文本。PDF 缺失不影响评测输入。

## 6. 改接线检查清单

1. 改 `run_batch` 计划构造或 refs staging → **同步改本文** §1–§2。  
2. 新增 01 stem → 登记 `PLAN_ITEM_TITLE` / `PLAN_TEMPLATE_ID` / `WORKFLOW_MAP` / `ARTIFACT_RELS` / scorer。  
3. 群里报 tip + 本文路径；操作员用约定模型 profile（如英伟达）开跑。


## 7. 会话注入日志（随案可查）

每一次工作流调用（每个 agent 轮次）必须有会话注入日志：**顶层 system / 工具 tools / 普通 user** 三段 + 各自成败。  
**不要**只去翻 serve 的 `.local/runs/...`；workspace 与 `result_dir` 也能带走。

| 落点 | 路径 |
|------|------|
| result_dir（首选） | `.benchmark/result/<cat>/<sub>/<case>/<run_id>/sessions/<leaf>/injection.{md,json}` + 同级 `work-record.{md,json}` |
| workspace 耐久 | `workspace/audit/runs/<run_id>/sessions/<leaf>/injection.{md,json}` + `work-record.*`（**按 run_id 分目录，后案不盖前案**） |
| workspace 当前 | `workspace/runs/_run/sessions/<leaf>/injection.{md,json}`（下一案 `prepare_fresh` 会清） |
| serve 快照 | `.local/runs/<run_id>/sessions/<leaf>/injection.{md,json}` |

`leaf` = `<node>[@revN].<agent>.<attempt>`。口径与查法详见 [`docs/ops/SESSION_INJECTION.md`](../../docs/ops/SESSION_INJECTION.md)。

## 8. workspace = 主仓单根

`run_batch.resolve_workspace()` **固定** `<主仓>/workspace`（与 tip-of-master serve 的 `PROJECT_ROOT/workspace` 一致）。  
**禁止**把 `.local/wt/serve/.../workspace` 当默认——曾因此拷走 WT 过期 `claims.json` 致 result_dir 假零分。

## 相关路径

| 项 | 路径 |
|----|------|
| 本规范 | `.benchmark/docs/PCFBENCH_EVAL_HOWTO.md` |
| run_batch | `.benchmark/scripts/run_batch.py` |
| import | `.benchmark/scripts/import_pcfbench_cases.py` |
| orch 01 | `.benchmark/{bom,lci}/harness/workflows/orchestrations/*-01.yaml` |
| scorers | `.benchmark/{bom,lci}/scorers/` |
| 会话注入口径 | `docs/ops/SESSION_INJECTION.md` |
