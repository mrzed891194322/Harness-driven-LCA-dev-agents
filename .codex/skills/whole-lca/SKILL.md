---
name: whole-lca
description: 通过初始化检查、前景清单提取、背景数据集映射、openLCA 导入与报告，无人值守地执行已有的 LCA 执行计划（plan.md）。适用于本仓库中的 whole-lca 或端到端 plan-to-LCIA 运行。
---

# 全生命周期评价（Whole-LCA）主工作流

将此技能作为 Codex 平台适配器使用。编排步骤以 `harness/workflows/LCA-main.md` 为唯一来源。不得在本 skill 中重述或弱化 workflow 内容。

## 启动

1. 仅使用 `workspace/inputs/plan.md` 作为计划输入；用户参考资料只从 `harness/knowledge/` 读取。当前 `codex exec` 会话即担任 `major-orchestrator`：先读取 `.codex/agents/major-orchestrator.toml` 的职责边界，再完整读取并执行 `harness/workflows/LCA-main.md`。GUI 或用户已前置 `clean_dir --preset whole-lca` 并完成文件就位；**不要**在 agent 内调用 `clean_dir` 或 MCP `cleanup_output`。不要再 spawn 另一个 `major-orchestrator`。
2. 只生成 `sub-executor` 和 `eval-reviewer`。每次委派前后在用户可见输出中写明当前阶段、被委派角色、输入产物路径和等待原因；子 Agent 返回后立即摘要结论与产物，不要用空的 Wait 心跳代替阶段进展。

## Codex 运行时补充

- 规则由角色按 `harness/roles/` 自读 `harness/rules/injection.md` 加载；本 skill 与 workflow 不列出规则路径。
- `major-orchestrator` 仅可生成 `sub-executor` 和 `eval-reviewer`，等待其返回并按 workflow 持久化证据。
- 如果返回 `failed`，保留已记录状态并报告 `status_reason` 与确切问题。终止只有 `completed` 和 `failed`。
- 运行启动即授权在当前预检范围完全一致时执行导入；预检通过后立即继续导入与报告，不得请求额外确认。
- 工作流产物保存在 `workspace/memory/`、`workspace/outputs/inventory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/`。

## 禁止

- 不得在本 skill 中复制四阶段步骤、阶段 spec 路径列表或 schema 加载顺序（均由 workflow 定义）。
