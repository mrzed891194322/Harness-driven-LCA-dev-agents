# 会话级注入文档（per-agent session）

对齐 `docs/architecture/DESIGN.md` 注入顺序：**顶层规则 → 工具/技能 → 任务上下文用户消息**。  
口径是「今天实际注入了什么 + 成败」，**不是** 10-10 的 intended↔effective。  
pi-runtime 的 `injection/first_request.json` 仅作对照；**宿主必须自写**本会话文档。

## 路径（三处；内容同构）

每个 agent 轮次一份目录（leaf = `<node>[@revN].<agent>.<attempt>`）：

```text
# 1) serve / 仓侧快照（原有）
.local/runs/<run_id>/sessions/<leaf>/
  injection.md    # 人读：三段内容 + 成功/失败
  injection.json  # 同结构机器可读（schema harness.injection.session/2）

# 2) workspace 当前跑（随 GUI / events；下一案 prepare_fresh 会清 runs/）
workspace/runs/_run/sessions/<leaf>/
  injection.md
  injection.json

# 3) workspace 按案耐久副本（prepare_fresh 不碰 audit/；多案互不覆盖）
workspace/audit/runs/<run_id>/sessions/<leaf>/
  injection.md
  injection.json
```

跑批 `result_dir`（`.benchmark/result/<cat>/<sub>/<case>/<run_id>/`）会再拷走：

```text
result_dir/
  work-record.json
  work-record.md
  sessions/<leaf>/injection.{md,json}
  artifacts/…
  status.json
  meta.json
```

实现：`backend.workflow.inject.write_session_injection_doc`（可传 `workspace=`）；在 `node_graph` 每轮 `turn_start` 前写出。  
`events.jsonl` 的 `session_doc` 优先指向 **workspace** 相对路径（`runs/_run/sessions/...`）。

## 三段字段

| 段 | label | 主要内容 | ok 条件 |
|----|-------|----------|---------|
| `system_prompt` | 顶层提示词 | global + inject + agent rules 路径、完整 system 正文、字符数 | 非空且规则加载无硬错误 |
| `tools` | 工具 | 文件工具清单、MCP、skills（名/路径/是否存在） | 声明的技能文件均存在 |
| `user_prompt` | 普通提示词 | plan/inputs/deliverable/rework 等分段标签 + 完整用户消息 | 非空 |

兼容：仍带 `planned` / `actual`（规则路径级），供旧 work-record 摘要。

## work-record（勿被后案整份盖掉）

| 落点 | 行为 |
|------|------|
| `workspace/runs/_run/work-record.{json,md}` | 当前跑 GUI 摘要；下一案会被清掉/覆盖 |
| `workspace/audit/runs/<run_id>/work-record.{json,md}` | **按 run_id 分文件**，后案不覆盖前案 |
| `result_dir/work-record.{json,md}` | 跑批收口拷走，随案归档 |

实现：`backend.workflow.work_record.write_work_record`。

## events.jsonl

`kind: injection` 事件携带与上表同构的结构化字段（正文截断为摘要元数据，全文在 session 文档）：

- `schema`, `ok`
- `planned`, `actual`（规则）
- `sections.{system_prompt,tools,user_prompt}`：各含 `ok` / `label` / `errors`，以及 paths/chars 或 skills/mcp 或 segments
- `session_doc`：相对路径（优先 workspace `runs/_run/sessions/...`）

## 怎么查（最短路径）

1. **随案**：打开本案 `result_dir/sessions/*/injection.md` 与 `result_dir/work-record.md`。  
2. **workspace 耐久**：`workspace/audit/runs/<run_id>/sessions/*/injection.md`。  
3. **serve 现场**：`.local/runs/<run_id>/sessions/*/injection.md`（或 serve WT 下同相对路径）。  
4. **当前跑**：`workspace/runs/_run/sessions/*/injection.md`（仅当该 run 尚未被下一案清掉）。

## 自检

短烟：对任一 01 工作流调用 `Injector.build_session_injection_report` + `write_session_injection_doc(..., workspace=ws)`，应在 `.local/runs/...`、`workspace/runs/_run/sessions/...`、`workspace/audit/runs/<run_id>/sessions/...` 三处看到两文件；`events` 接线后出现 `injection`。
