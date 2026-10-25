# lci（mapping）

大类目录：`.benchmark/lci/`。子类 `mapping/<case_id>/`。

## 离线打分

```bash
python3 .benchmark/bom/scorers/score_case.py --mode score-only --suite lci
```

`--suite mapping` 仍可作为 `lci` 的别名。

## 路径

- 题面：`lci/mapping/<case_id>/input/query.md`
- 真值：`lci/mapping/<case_id>/truth/mapping.json`
- 假产物：`lci/mapping/<case_id>/eval/artifacts/mapping.json` 与 `events.jsonl`

交付形状见 `.benchmark/schemas/mapping_deliverable.schema.json`。
打分器：`.benchmark/lci/scorers/fabrication_rate.py`。
