# mapping

合成的背景映射。对应以后的 PCFBench task3。P0 的候选集写在每个案例的 `expected/mapping.json`，不是 2574 行 picklist。

## 跑

```bash
python3 .benchmark/scorers/score_case.py --mode score-only --suite mapping
```

## 目录

- 题面：`suites/mapping/cases/<case_id>/input/query.md`
- 真值：`expected/mapping.json`，含封闭 `candidates`、每行 `options` 和可选 `banned_substring`
- 假产物：`fixtures/mapping/<case_id>/artifacts/mapping.json`（字段对齐 harness 的 mapping 交付）和 `events.jsonl`

打分只认 expected 里的候选集。交付物上的 `candidates` 不能用来证明自己没编造。

命中：`process_id` 或 `provider_id` 对上候选 id，或 `process_name` / `provider_name` 与候选名规范化后相同。否则只要写了过程名或 id，就算编造。没写过程名也没写 id 则是弃权，不算编造。`exact_match_rate` 另看 `options`。

## 两条 fixture

| case_id | 预期 |
| --- | --- |
| `map-low-alloy-steel` | 选中候选集内的 low-alloyed。`candidate_hit_rate` = 1，`fabrication_rate` = 0，`exact_match_rate` = 1。事件 1 次 `submit_rejected` |
| `map-invented-resin` | 过程名 `magic resin 9000` 不在候选集，且踩了 `banned_substring`。`fabrication_rate` = 1，`banned_violation_rate` = 1。事件 1 次 `redo_approved` |

交付形状见 `.benchmark/schemas/mapping_deliverable.schema.json`。

picklist 全文用下载脚本放到 `$BENCHMARK_CACHE`，不要提交 `ecoinvent_picklist.jsonl`。
