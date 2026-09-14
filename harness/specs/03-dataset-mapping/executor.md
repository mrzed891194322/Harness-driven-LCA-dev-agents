# 03 背景映射与 LCI（执行）

按本阶段共有契约写出 mapping 与可导入 LCI。审查通过前禁止 `import_lci`。

## 需要解决的问题

- 首次调用 openLCA 前做 `health_check`。名称与 UUID 必须用正式工具查询，禁止编造。
- 不得用错误功能冒充（再生粒料不得代替原生，除非计划要求）。
- 精确地域无候选时自行选区域市场或 `RoW`/`GLO`，记下请求值、选用值和理由。
- 可留档的匹配自行选择并写入 mapping。
- 写出 `process-mapping.json` 与 `workspace/outputs/LCI/`（含 `human_readable_mapping.md`），JSON-LD 字段以共有契约为准。

## 返工方式

在原执行会话中根据审查意见返工：只改指出的映射行或 LCI 实体，重新提交完整产物与修改说明。不要在本阶段导入。最新落盘文件才是本轮交付。

## 提交

handoff：`role=executor`，`status` 为 `ok` / `failed` / `blocked`，`artifacts` 列出 mapping 与 LCI 路径。

确定性检查由主编排在本轮 handoff 后执行。可选用 `get_validation_state("mapping")` / `validate_artifacts("mapping")` 做提前反馈，不是提交 `ok` 的前提。只引用工具生成的检查，不自报权威校验计数。
