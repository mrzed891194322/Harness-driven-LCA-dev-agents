# lci（mapping / triage）

大类目录：`.benchmark/lci/`。子类 `mapping/<case_id>/`、`triage/<case_id>/`。

## 离线打分

```bash
python3 .benchmark/bom/scorers/score_case.py --mode score-only --suite lci
# 或扫真跑产物：
uv run python .benchmark/scripts/score_batch.py --category lci
```

`--suite mapping` 仍可作为 `lci` 的别名（score_case）；triage 主指标 accuracy。

## 路径

### mapping（task3）

- 题面：`lci/mapping/<case_id>/input/query.md`
- 真值：`lci/mapping/<case_id>/truth/mapping.json`
- 假产物：`lci/mapping/<case_id>/eval/artifacts/mapping.json` 与 `events.jsonl`
- 交付：`.benchmark/schemas/mapping_deliverable.schema.json`
- 打分：`.benchmark/lci/scorers/fabrication_rate.py`
- orch：`lci-mapping-03`（薄注入+reviewer）/ `lci-mapping-04`（最好）；01/02 未建

### triage（task2）

- 题面：`lci/triage/<case_id>/input/query.md`
- 真值：`lci/triage/<case_id>/truth/triage.json`
- 交付：`.benchmark/schemas/triage_deliverable.schema.json`
- 打分：`.benchmark/lci/scorers/triage_accuracy.py`（主指标 accuracy）
- orch：`lci-triage-03`（薄注入+reviewer）/ `lci-triage-04`（最好）；01/02 未建
- 导入：`python3 .benchmark/scripts/import_pcfbench_cases.py --task task2 --limit 10`
