# 03 背景映射与 LCI 修订（执行）

按本阶段共有契约与修订补充契约写出完整 mapping 与可导入 LCI。审查通过前禁止 `import_lci`。不要覆盖 `plan.md`。

## 需要解决的问题

- 同时读取最新 BOM、上一轮 `process-mapping.json` 与 `workspace/outputs/LCI/`、`plan.md` 与 `revise.md`。
- `revise.md` 与原计划或旧映射冲突时以 `revise.md` 为准。
- 首次调用 openLCA 前做 `health_check`。受用户意图影响的映射行必须重新正式查询名称与 UUID，禁止沿用已过时或臆造的 UUID。
- 不得留下与用户意图矛盾的旧 Process / Flow / Provider；未点名且仍对应现行 BOM 的映射可保留，但须写入本轮完整产物。
- 写出完整 `process-mapping.json` 与完整 canonical `workspace/outputs/LCI/`（含 `human_readable_mapping.md`），不要只交差量实体。

## 返工方式

在原修订会话中根据审查意见返工：先改意图缺口，再改指出的映射行或 LCI 实体，重新提交完整产物。不要在本阶段导入。最新落盘文件才是本轮交付。

## 提交

handoff：`role=reviser`，`status` 为 `ok` / `failed` / `blocked`，`artifacts` 列出 mapping 与 LCI 路径。

确定性检查由主编排在本轮 handoff 后执行。可选用 `get_validation_state("mapping")` / `validate_artifacts("mapping")` 做提前反馈，不是提交 `ok` 的前提。只引用工具生成的检查，不自报权威校验计数。
