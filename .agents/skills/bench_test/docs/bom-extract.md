# bom-extract

合成的数量抽取。对应以后要从 PCFBench task4（物料）和 task5（能耗）转写的案例。P0 不读缓存。

## 跑

```bash
python3 .benchmark/scorers/score_case.py --mode score-only --suite bom-extract
```

## 目录

- 题面：`suites/bom-extract/cases/<case_id>/input/query.md`
- 真值：同级 `expected/claims.json`（打分用）和 `expected/bom.json`（harness BOM 形状，P0 不比较内容，只在 fixture 侧做字段检查）
- 假产物：`fixtures/bom-extract/<case_id>/artifacts/claims.json`、`bom.json`、`events.jsonl`
- `meta.yaml`：自建 `case_id`；`pcfbench_id` 在 P0 是虚构的

## 两条 fixture

| case_id | 预期 |
| --- | --- |
| `bom-steel-plate` | 两条真值都命中，另有一条 99 kg 幻觉。F1 = 0.8。事件里 1 次 reject、1 次 redo，`c4_if` = 2 |
| `bom-film-roll` | 预测用 `1500 g`，应与真值 `1.5 kg` 算同一条。能耗没交。F1 = 2/3。事件里没有 reject/redo |

声明形状见 `.benchmark/schemas/claim_set.schema.json`。BOM 形状见 `bom_deliverable.schema.json`。

## 拒答（abstention）

套件 `abstention` 的案例用 `paired_case_id: bom-steel-plate` 指向上面的钢板案例，但 `input/query.md` 写明没有来源文档。

```bash
python3 .benchmark/scorers/score_case.py --mode score-only --suite abstention
```

| case_id | 假产物 | 预期 |
| --- | --- | --- |
| `abstain-steel-plate-nodoc` | `abstained: true` 且 `claims: []` | `abstention_correct` true，F1 = 1 |
| `abstain-steel-plate-leaked` | 在没有文档时仍写出 12.5 kg | `abstention_correct` false，F1 = 0 |

不要把 PCFBench 的 jsonl 抄进这两个套件。要上游原文时走 `.agents/skills/bench_test` 的 `fetch`，文件留在 `$BENCHMARK_CACHE`。
