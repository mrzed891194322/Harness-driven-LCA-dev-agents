# 会话级注入文档（per-agent session）

对齐 `docs/architecture/DESIGN.md` 注入顺序：**顶层规则 → 工具/技能 → 任务上下文用户消息**。  
口径是「今天实际注入了什么 + 成败」，**不是** 10-10 的 intended↔effective。  
pi-runtime 的 `injection/first_request.json` 仅作对照；**宿主必须自写**本会话文档。

## 路径

每个 agent 轮次一份目录（与 pi `sessionSnapshotDir` 一致）：

```text
.local/runs/<run_id>/sessions/<node>[@revN].<agent>.<attempt>/
  injection.md    # 人读：三段内容 + 成功/失败
  injection.json  # 同结构机器可读（schema harness.injection.session/2）
```

实现：`backend.workflow.inject.write_session_injection_doc`；在 `node_graph` 每轮 `turn_start` 前写出。

## 三段字段

| 段 | label | 主要内容 | ok 条件 |
|----|-------|----------|---------|
| `system_prompt` | 顶层提示词 | global + inject + agent rules 路径、完整 system 正文、字符数 | 非空且规则加载无硬错误 |
| `tools` | 工具 | 文件工具清单、MCP、skills（名/路径/是否存在） | 声明的技能文件均存在 |
| `user_prompt` | 普通提示词 | plan/inputs/deliverable/rework 等分段标签 + 完整用户消息 | 非空 |

兼容：仍带 `planned` / `actual`（规则路径级），供旧 work-record 摘要。

## events.jsonl

`kind: injection` 事件携带与上表同构的结构化字段（正文截断为摘要元数据，全文在 session 文档）：

- `schema`, `ok`
- `planned`, `actual`（规则）
- `sections.{system_prompt,tools,user_prompt}`：各含 `ok` / `label` / `errors`，以及 paths/chars 或 skills/mcp 或 segments
- `session_doc`：相对仓根的会话目录路径

跑级 `workspace/runs/_run/work-record.{md,json}` 会汇总上述 `injection` 事件（含 `session_doc` 与三段 ok）。

## 自检

短烟：对任一 01 工作流调用 `Injector.build_session_injection_report` + `write_session_injection_doc`，应在 `.local/runs/<id>/sessions/.../` 看到两文件，且 `events` 接线后出现 `injection`。
