# 本系统如何跑 PCFBench / 评测（规范）

> **权威口径**（Du Yuan 2026-10-28）。设计与改工作流以本文为准；改 `run_batch` / import / 01 接线须**同步改本文**。  
> 任务子集与抽案细节另见 [`../PCFBENCH_T123_01.md`](../PCFBENCH_T123_01.md)、[`../RUNBOOK.md`](../RUNBOOK.md)。

## 1. 计划（全任务 01）

**禁止**把 `query.md` 原文当作 `/api/workflow/start` 的裸 `plan` 字符串糊进去。

须发合法 YAML items（由 `run_batch.build_plan_start_body` 构造）：

```yaml
kind: lca_execution_plan
version: 2
template_id: bom-only   # 或 lca-only / 自定 minimal；extract 默认 bom-only，lci-* 默认 lca-only
items:
  - title: 文献提取      # 可自拟；triage 默认「映射分流」，mapping 默认「LCI封闭集映射」
    content: |           # = 本案 input/query.md 全文
      …
```

等价 JSON 请求体：

```json
{
  "workflow": "bom-extract-01",
  "plan": "",
  "template_id": "bom-only",
  "items": [{"title": "文献提取", "content": "<query.md 全文>"}]
}
```

适用：`bom-extract-01`、`lci-triage-01`、`lci-mapping-01`（及同族 01）。

## 2. 上传（references）

上传走 `POST /api/references`，`types` 与文件一一对应。`run_batch.stage_case_references` 实现下列规则。

| 任务 | 规则 |
|------|------|
| **T4/T5 extract** | 只挂 **一份** `input/reference.md`，`type=knowledge`。**去掉** stem 同文别名（`.md` / `.txt` / 伪 PDF 名）。**不**挂 BOM。 |
| **T2 triage / T3 mapping** | 有 BOM 素材文件 → `type=bom`；仅有 `reference.md` → `knowledge`；都没有 → **可不上传**（题面写进计划 items 即可）。 |

开跑前会清空已有 references，再按上表挂本案文件。

## 3. 01 薄档怎么跑

01 = 真薄：无 reviewer / 无 skills / 无 node.inject；全局交卷规则仍由宿主注入。

| stem | cases-root（全量/抽样子集） | 主产物 | 主指标 |
|------|------------------------------|--------|--------|
| `bom-extract-01` | `.benchmark/imported/bom/extract/` | `artifacts/bom/claims.json` | Claim F1 |
| `lci-triage-01` | `.benchmark/imported/lci/triage/` | `artifacts/triage/triage.json` | `triage_accuracy` |
| `lci-mapping-01` | `.benchmark/imported/lci/mapping/` | `artifacts/mapping/mapping.json` | **Top-1** = `mean_top1` |

```bash
# 例：extract 01（英伟达 profile_id 替换 <profile>）
uv run python .benchmark/scripts/run_batch.py --model <profile> \
  --workflow bom-extract-01 \
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

## 4. serve / tip 要点

- 跑批读的是 **serve worktree** 上的 tip；主仓 tip ≠ 自动切服。空窗再 `checkout` 目标 tip 并重启 8800/3000。
- 验 01 接线至少含：`build_plan_start_body` + 无别名的 `stage_case_references`（见 tip 说明）。
- 本轮先做 **01**，不追 02–04 厚档。
- 缺 `reference.md` 的 extract 案可进 `knowledge_skip`（不烧配额空转）。

## 5. 改接线检查清单

1. 改 `run_batch` 计划构造或 refs staging → **同步改本文** §1–§2。  
2. 新增 01 stem → 登记 `PLAN_ITEM_TITLE` / `PLAN_TEMPLATE_ID` / `WORKFLOW_MAP` / `ARTIFACT_RELS` / scorer。  
3. 群里报 tip + 本文路径；操作员用约定模型 profile（如英伟达）开跑。

## 相关路径

| 项 | 路径 |
|----|------|
| 本规范 | `.benchmark/docs/PCFBENCH_EVAL_HOWTO.md` |
| run_batch | `.benchmark/scripts/run_batch.py` |
| import | `.benchmark/scripts/import_pcfbench_cases.py` |
| orch 01 | `.benchmark/{bom,lci}/harness/workflows/orchestrations/*-01.yaml` |
| scorers | `.benchmark/{bom,lci}/scorers/` |
