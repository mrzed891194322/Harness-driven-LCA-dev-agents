# Whole-LCA 运行、状态与证据公共契约

## 1. 状态机

合法 manifest 状态为：`not_started`、`running`、`needs_input`、`needs_review`、`failed`、`completed`。

执行顺序固定为：

1. `01-plan-quality-gate`：计划质量门禁；
2. `02-evidence-retrieval`：资料与 openLCA 候选检索；
3. `03-lci-construction`：LCI 制定；
4. `04-lci-quality-evaluation`：LCI 质量评估与定向修正；
5. `05-openlca-preflight-confirmation`：openLCA 写入预检（保留既有包名作为兼容标识）；
6. `06-openlca-import-readback`：导入与模型图读回；
7. `07-lcia-calculation-reporting`：LCIA 计算、结果验收与报告。

不得跳过计划审查、LCI 审查或写入预检。启动 whole-LCA 即授权在当前预检哈希与范围完全一致时执行导入；运行中不得请求额外确认。各阶段的进入、通过和受控停止条件由对应编号规范定义。

## 2. 固定运行目录

- 运行记忆根目录：`workspace/memory/`。
- LCI 根目录：`workspace/outputs/LCI/`。
- 结果根目录：`workspace/outputs/reports/`。
- 初始化时创建 `manifest.json`，记录计划路径与 SHA-256、平台、主 agent、状态和产物索引。
- 阶段文件写入 `stages/<三位序号>-<stage>.json`；交接写入 `handoffs/<三位序号>-<from>-to-<to>.json`。
- 计划审查固定为 `reviews/plan-review.json`；LCI 审查为 `reviews/lci-review-<attempt>.json`。
- 阶段、审查和交接记录一经写入不得覆盖。需要修订时创建后续序号文件，并用 issue ID 和 artifact hash 建立关联。

运行开始前的旧产物清理由外部流程负责。工作流使用上述固定路径，不生成运行 ID 或按运行 ID 分层；如果旧文件仍然存在，固定文件可以被本次运行覆盖，但同一次运行内不得覆盖已有阶段、审查或交接历史。

所有时间戳使用带 `Z` 的 RFC 3339 UTC 格式。所有文件哈希使用小写 64 位 SHA-256。

## 3. Agent 交接

每次委派前后都在 `workspace/memory/handoffs/` 保存符合 `handoff.schema.json` 的记录，至少包含 schema/version、handoff/stage ID、from/to agent、时间、输入产物及 SHA-256、来源 artifact ID、`revision_of`/`supersedes_*` 修订关联、决策、证据引用、未解决项、状态、下一动作和关联 issue ID。初始记录的修订关联显式写为 `null` 或空数组，不得省略。受委派 Agent 可按任务需要读取相关记忆，但只有主编排 Agent 负责持久化运行状态和历史记录。

## 4. 通用终止状态

- `completed`：第 07 阶段的全部完成条件已有结构化证据。
- `needs_input`：必须由用户补充范围或事实才能继续。
- `needs_review`：达到审查上限或结果需人类判断。
- `failed`：已授权的执行发生不可恢复的工具、导入或计算失败，证据已持久化。

不得因文件存在、工具返回 exit 0 或 agent 自称完成而标记 `completed`。
