---
name: whole-lca
description: 通过分阶段的计划接收、证据检索、最多三次 LCI 审查循环、openLCA 写入预检、自动导入回读、LCIA 计算及结果归档，来无人值守地执行已有的 LCA 执行计划（plan.md）。适用于本仓库中的 whole-lca 或端到端 plan-to-LCIA 运行。
---

# 全生命周期评价（Whole-LCA）主工作流

将此技能作为 Codex 平台适配器使用。运行契约、阶段规则与结果结构以 `harness/specs/public/` 与 `harness/specs/01-*` 至 `07-*` 为准；编排步骤以 `harness/workflows/LCA-main.md` 为唯一来源。不得在本 skill 中重述或弱化 workflow 内容。

## 启动

1. 执行下列脚本清理 openLCA 与 workspace 生成文件（如有）：
   `uv run python harness/tools/control_openlca/cleanup_output/main.py --yes`
   `uv run python src/scripts/clean_dir/main.py --yes --target workspace_without_inputs`
2. 仅使用 `workspace/inputs/plan.md` 作为计划输入。当前 `codex exec` 会话即担任 `major-orchestrator`：先读取 `.codex/agents/major-orchestrator.toml` 的职责边界，再完整读取并执行 `harness/workflows/LCA-main.md`。不要再 spawn 另一个 `major-orchestrator`。
3. 只生成 `sub-executor` 和 `eval-reviewer`。每次委派前后在用户可见输出中写明当前阶段、被委派角色、输入产物路径和等待原因；子 Agent 返回后立即摘要结论与产物，不要用空的 Wait 心跳代替阶段进展。

## Codex 运行时补充

- LCA 知识与 openLCA 规则在 Codex 中均不全局加载；按 workflow 条件读取 `harness/rules/lca-knowledge/README.md` 与 `harness/rules/openlca-operation/README.md`。
- `major-orchestrator` 仅可生成 `sub-executor` 和 `eval-reviewer`，等待其返回并按 workflow 持久化证据。
- 如果返回 `failed`，保留已记录状态并报告 `status_reason` 与确切问题。终止只有 `completed` 和 `failed`。
- 运行启动即授权在当前预检范围完全一致时执行导入；预检通过后立即继续第 06 阶段，不得请求额外确认。
- 工作流产物保存在 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/`。

## 禁止

- 不得在本 skill 中复制七阶段步骤、阶段 spec 路径列表或 schema 加载顺序（均由 workflow 定义）。
