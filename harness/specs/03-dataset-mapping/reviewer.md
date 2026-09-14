# 03 映射与 LCI 审查

按本阶段共有契约独立核对 mapping 与 LCI，不修改被审文件，不执行导入。

## 证据核对

- 映射是否功能对应；不得用错误功能冒充（再生粒料不得代替原生，除非计划要求）。
- 选用理由、请求地域与实际地域是否写清。
- LCI 实体能否对上 BOM `item_id`。明显错配则 `failed` 并指出要改的行。
- UUID 必须能指回正式查询，禁止臆造。审查通过前不得把已导入当成阶段完成。

## 复审

必须重新读取最新 `process-mapping.json` 与 `workspace/outputs/LCI/`，核实原问题是否解决，并检查修改是否引入新问题。历史对话中的产物内容和旧结论不能替代本轮核对。

## 返工意见

`fix_instructions` 定位到 `item_id`、JSON-LD 文件或 UUID 缺口。

## 提交

handoff：`status` 为 `passed` 或 `failed`。

主编排已运行本阶段确定性检查。可用 `get_validation_state("mapping")` 查看状态，不必把工具成功当作审查通过。只引用工具生成的检查，不自报权威校验计数。
