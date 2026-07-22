# Whole-LCA 运行、状态与证据契约

## 1. 状态机

合法 manifest 状态为：`not_started`、`running`、`awaiting_confirmation`、`needs_input`、`needs_review`、`failed`、`completed`。

执行顺序固定为：

1. 初始化 run；
2. 计划接收审查；
3. 资料与 openLCA 候选检索；
4. LCI 构建；
5. LCI 审查/定向修正循环；
6. openLCA 写入预检；
7. 用户确认门禁；
8. 导入；
9. 模型图读回；
10. 产品系统 LCIA 计算；
11. 结果验收与报告。

不得跳过计划审查、LCI 审查、预检或用户确认。终止状态只能按本规范和结果规范决定。

## 2. Run ID 与目录

- `run_id` 格式为 `YYYYMMDDTHHMMSSZ-<8 位小写十六进制>`；时间使用 UTC。
- 日志根目录：`workspace/logs/whole-lca/<run_id>/`。
- 结果根目录：`workspace/results/<run_id>/`。
- 初始化时创建 `manifest.json`，记录计划路径与 SHA-256、平台、主 agent、状态和产物索引。
- 阶段文件写入 `stages/<三位序号>-<stage>.json`；交接写入 `handoffs/<三位序号>-<from>-to-<to>.json`。
- 计划审查固定为 `reviews/plan-review.json`；LCI 审查为 `reviews/lci-review-<attempt>.json`。
- 阶段、审查和交接记录一经写入不得覆盖。需要修订时创建后续序号文件，并用 issue ID 和 artifact hash 建立关联。

所有时间戳使用带 `Z` 的 RFC 3339 UTC 格式。所有文件哈希使用小写 64 位 SHA-256。

## 3. Agent 交接

每次委派前后都保存符合 `handoff.schema.json` 的记录，至少包含 schema/version、run/handoff/stage ID、from/to agent、时间、输入产物及 SHA-256、来源 artifact ID、`revision_of`/`supersedes_*` 修订关联、决策、证据引用、未解决项、状态、下一动作和关联 issue ID。初始记录的修订关联显式写为 `null` 或空数组，不得省略。

检索交接还必须记录：查询词、候选项、选择理由、来源文件/章节或数据库实体 UUID、查询时间和未解决项。RAG 命中只作为定位线索，关键事实须回读原文并记录位置。

## 4. LCI 审查循环

- 审查依据包括计划目标、`lci-construction` spec、JSON 模板和映射报告模板。
- 每个问题使用跨轮次稳定的 `LCI-...` issue ID；修正不得重命名仍未解决的问题。
- 最多执行 3 次 LCI 审查，attempt 依次为 1、2、3。
- attempt 1 或 2 未通过：只把仍未解决的问题和受影响产物委托给 `sub-executor` 定向修正，再进入下一次审查。
- attempt 3 未通过：不得进行第 4 次修正或审查；保存问题，manifest 置为 `needs_review` 并停止。
- 只有 review 状态 `passed` 且无 `critical`/`major` 未解决问题时才能进入预检。

## 5. 写入预检与确认

- 预检必须使用 `preflight_import_lci`，并保存完整返回值、`preflight_hash`、活动数据库标识、目标分类、待创建实体及覆盖/删除范围。
- manifest 置为 `awaiting_confirmation`，向用户原样展示数据库、分类、创建数量、覆盖/删除实体和预检哈希，并请求当场确认。
- 用户拒绝、未确认或只给出模糊授权时，保留已通过审查的 LCI，manifest 置为 `needs_review`，不得调用 `import_lci`。
- 确认只覆盖该预检哈希对应的范围。导入前重新预检；文件、数据库目标、分类或覆盖范围变化时哈希必须变化，旧确认立即失效。

## 6. 终止条件

- `completed`：导入无失败、模型图无断链、LCIA 原始结果非空，且全部必需结果文件通过 schema/模板验收。
- `needs_input`：必须由用户补充范围或事实才能继续。
- `needs_review`：达到审查上限、用户未授权写入、范围变化需要重确认，或结果需人类判断。
- `failed`：已授权的执行发生不可恢复的工具/导入/计算失败，证据已持久化。

不得因文件存在、工具返回 exit 0 或 agent 自称完成而标记 `completed`。
