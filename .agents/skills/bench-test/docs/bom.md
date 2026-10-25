# bom（抽取 + 拒答）

大类目录：`.benchmark/bom/`。案例在 `cases/<case_id>/`（`meta.yaml`、`input/`、`truth/`、`eval/`）。

拒答案例与抽取案例同树：`meta.tags` 含 `abstention`，并用 `paired_case_id` 指向配对抽取案例。

## 离线打分

```bash
python3 .benchmark/bom/scorers/score_case.py --mode score-only --suite bom
python3 .benchmark/bom/scorers/score_case.py --mode score-only --suite abstention
python3 .benchmark/bom/scorers/score_case.py --mode score-only --self-check
```

`--suite bom-extract` 仍可作为 `bom`（非拒答）的别名。

## 路径

- 题面：`bom/cases/<case_id>/input/query.md`
- 真值：`bom/cases/<case_id>/truth/claims.json`（及可选 `bom.json`）
- 假产物：`bom/cases/<case_id>/eval/artifacts/claims.json`、`bom.json`、`events.jsonl`
- 冒烟 orch：`.benchmark/bom/harness/workflows/orchestrations/bom-extract.yaml`

声明形状见 `.benchmark/schemas/claim_set.schema.json`。BOM 形状见 `bom_deliverable.schema.json`。

## 拒答

正确交付是 `abstained=true` 且 `claims` 为空。有声明即算没有拒答。打分器报告 `scores.abstention.abstention_correct`。
