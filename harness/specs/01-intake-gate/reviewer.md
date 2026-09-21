# 01 初始化检查（审查）

按本阶段共有契约独立核对证据并给出结论。不要修改计划或知识目录中的文件。

## 需要解决的问题

- `workspace/inputs/plan.md` 能否启动端到端：研究对象与目的、功能单位的数值+描述+单位、系统边界、截断或明确不截断、多产出/分配、预期应用或完成判断。
- 本任务 `source_manifest` / `knowledge_sources`：先按声明来源核对再下结论。计划里点名的资料必须对得上文件。声明来源为空且计划声称有资料则 `failed`。
- 不要因为计划缺少内部符号（如 `GAP-*`）而失败。
- 本阶段不调 `health_check`、不写 BOM、不查库、不导入。

## 返工意见

本阶段不返工。未通过则 `failed`，在 `status_reason` 与 `fix_instructions` 写明缺什么或何处矛盾。

## 提交

写 handoff：`role=reviewer`，`status` 为 `passed` 或 `failed`，`status_reason` 非空。失败时 `fix_instructions` 定位到计划章节或缺失文件。
