# 02 前景清单提取（执行）

按本阶段共有契约写出 BOM。不要查询 openLCA、不要写 LCI。

## 需要解决的问题

- 直接读取本任务配置的资料来源（运行上下文的 `knowledge_sources` / `source_manifest`；若已注册外部检索工具，也可按该来源工作）。
- 读得出的文本/表格必须抽取并记下 `source_locations`。
- 读不出的二进制标为 `unreadable`，不得编造数量。
- 写出 `extracted-bom.json` 与 `extracted-bom.md`，字段以共有契约为准。

## 返工方式

若在原执行会话中收到审查意见：只修正指出的行或缺口，重新提交完整 BOM 与 handoff。不要另起一套清单。历史对话中的旧 BOM 不能替代本轮落盘文件。

## 提交

写 handoff：`role=executor`，`status` 为 `ok` / `failed` / `blocked`，列出 `artifacts`。`status_reason` 非空。

确定性检查由主编排在本轮 handoff 后执行。可选用 `get_validation_state("inventory")` / `validate_artifacts("inventory")` 做提前反馈，不是提交 `ok` 的前提。只引用工具生成的检查，不自报权威校验计数。
