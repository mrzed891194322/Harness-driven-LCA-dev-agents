# v5 前端对照表（参考版本 master `599ed0a`）

目的：恢复旧页面前，逐页逐块列出旧版显示什么、v5 由哪个接口供数、哪些旧块在 v5 没有数据。
**没有数据的块不删除、不编造，列给 Du Yuan 决定。** 旧截图参考主仓库 `.local/ui-op/`。

| 页面 | 旧版块（599ed0a） | 旧版数据来源 | v5 数据来源 | 状态 |
|---|---|---|---|---|
| 顶栏 | Harness 按钮、设置、教程入口 | — | — | 已恢复 |
| /runs | 运行头：状态徽标、开始/停止 | `/api/workflow/progress`、`start`、`stop` | `/api/v5/status`、`/api/workflow/start`、`stop`、`/api/v5/resume` | 已有（run-panel） |
| /runs | 右侧阶段列表 run-side（阶段卡、实时点、第 N 次、阶段动作按钮） | `/api/workflow/progress` | `/api/v5/status` 的 nodes（status、rounds） | 已恢复（I-42），节点表保留 |
| /runs | 阶段动作「从检查点续跑本阶段」 | 旧版本就未接入（按钮 disabled） | 无 | **无数据，待决定** |
| /runs | 活动概览 activity-summary（各分工 chip、正在执行/历史、最后一条细节） | `/api/workflow/activity`（轮询） | `/api/v5/events`（node、role、kind、ts、detail） | 已恢复（I-42）；工具调用次数无数据，改显示模型重试/被拒/提醒次数 |
| /runs | 代理输出流 agent-stream（逐条消息、工具调用、思考、AgentProse 渲染） | `/api/workflow/activity` 返回的代理日志文本（parseAgentLog） | 无接口。数据在磁盘 `.local/runs/<run>/sessions/<node.role>.<n>/transcript.jsonl` | **无 v5 接口**：需新增只读会话输出接口（如 `/api/v5/sessions/<node>/<role>/<round>`，可选 SSE）后才能恢复，待决定 |
| /runs | 失败/中断原因弹窗 run-reason-panel | progress 的 reason | `/api/v5/status` 的 reason、节点 error、`turn_aborted` 事件 detail | 已恢复弹窗（I-42） |
| /runs | turnFailureKind（模型连接失败 / 没有交接） | 代理日志文本 | `model_retry`、`turn_aborted`(model_error) 事件 | 已并入失败原因弹窗（I-42） |
| /plan | 研究表单 StudyForm | `/api/plan` | `/api/plan` | 已有 |
| /plan | PreviewBoard：环境 | `/api/diagnostics/environment` | 同左 | 已恢复（I-41） |
| /plan | PreviewBoard：工作流 / 工作内容 | `/api/harness/document` | `/api/v5/workflows`、`/api/v5/harness` | 已恢复（I-41） |
| /plan | WorkflowBoard：默认模型、各阶段模型 | `/api/workflow/models`、`/api/models/selection` | 同左（v5 只有全局模型，无逐节点模型） | 已恢复：默认模型 + 逐代理模型/思考（`/api/v5/agent-models`，I-41） |
| /plan | WorkflowBoard：全局规则、阶段规则、工具、知识源卡片 | `/api/harness/document` | `/api/v5/harness`（rules/roles/specs/workflows） | 已恢复（`/api/v5/workflows`） |
| /plan | InjectionBoard：生成提示、权限、合并说明、锁定/知识/MCP 标记 | `/api/harness/injection` | 无。v5 注入在 `backend/v5/inject.py` 运行时拼装，没有预览接口 | 已按指示在「预览执行」里加只读注入预览（`/api/v5/preview`，I-41）；旧版合并说明、锁定标记未恢复 |
| /results | 文件树、最终交付、工作记录、下载 | `/api/results*` | `/api/results*`（加 handoffs、previous） | 已有 |
| /status | 环境与连接检查 | `/api/diagnostics/environment`、`/api/lca/openlca` | 同左 | 已有 |
| /harness | 目录导航（分区/分组/条目）+ 文档阅读，harness-shell 布局 | `/api/harness/catalog`、`/api/harness/document` | `/api/v5/harness`（只读 YAML） | **已按旧版布局重做**（Q8）；旧版的 Markdown 文档渲染、图片 harness-figure 在 v5 无对应文档 |
| /harness | `/harness/[...slug]` 深链接 | 路由 | 无（单页内选择） | **待决定**是否恢复深链接 |

## 需要 Du Yuan 决定的无数据块
1. /runs 代理输出流：是否新增只读会话输出接口（轮询或 SSE）来恢复。
2. ~~注入预览~~、~~逐阶段模型~~：已按 Grok Bot 转达的要求在 /plan 实现（I-41），请 Du Yuan 确认。
4. /runs「从检查点续跑本阶段」：旧版本也没接入。
5. /harness 深链接和 Markdown 文档、图片渲染：v5 只有 YAML。
