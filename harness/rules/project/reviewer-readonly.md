# 审查只读

本规则约束审查任务。

- 只读被审对象与交接列出的输入；不要修改计划、BOM、mapping、LCI、报告或知识目录中的被审文件。
- 只提交审查结论与 handoff（`passed` / `failed`、`status_reason`、失败时的 `fix_instructions`）。
- 不要生成替代产物，不要委派其他 agent，不要执行导入或计算来“补做”执行任务。
- 复审时重新读取最新落盘产物；不要用对话历史中的旧内容代替本轮核对。

- 允许调用 lca_artifacts 生成独立审计文件及刷新检查状态；这些工具不得修改被审文件。禁止调用 render_report_tables。
- 复审先看变化项、failed/stale 检查及引用，再按需抽查完整证据。机器检查 passed 不代替功能等价性、范围合理性和语言质量判断。
