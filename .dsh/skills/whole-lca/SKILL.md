---
name: whole-lca
description: 通过初始化检查、前景清单提取、背景数据集映射、openLCA 导入与报告，无人值守地执行已有的 LCA 执行计划（workspace/inputs/plan.md）。适用于本仓库中的 whole-lca 或端到端 plan-to-LCIA 运行。
whenToUse: 用户要求运行 whole-lca、执行 LCA 计划，或从 workspace/inputs/plan.md 端到端生成 LCIA 报告时。
---

# 全生命周期评价（Whole-LCA）主工作流

将此技能作为 DSH 平台适配器使用。编排步骤以
`harness/workflows/LCA-main.md` 为唯一来源。不得在本 skill 中重述或弱化 workflow 内容。

## 启动

1. 仅使用 `workspace/inputs/plan.md` 作为计划输入；用户参考资料只从 `harness/knowledge/` 读取。当前 headless 会话即担任 `major-orchestrator`：先完整读取 `harness/roles/major-orchestrator.md` 的职责边界，再完整读取并执行 `harness/workflows/LCA-main.md`。GUI 或用户已前置 `clean_dir --preset whole-lca` 并完成文件就位；**不要**在 agent 内调用 `clean_dir` 或 MCP `cleanup_output`。不要再生成另一个主编排。
2. 只生成 `sub-executor` 和 `eval-reviewer` 两个角色的子 agent。每次委派前后在用户可见输出中写明当前阶段、被委派角色、输入产物路径和等待原因；子 agent 返回后立即摘要结论与产物，不要用空的 Wait 心跳代替阶段进展。

## DSH 运行时补充

- workflow 文本中的 MCP 裸工具名在 DSH 中带前缀：`mcp__control_openlca__health_check` 等（`mcp__control_openlca__<原名>`）。若工具列表中不存在 `mcp__control_openlca__*` 工具，视为 openLCA 不可用：按 workflow 将运行置为 `failed` 并写非空 `status_reason`，不得绕过或重试。
- 子 agent 用 `subagent` 工具生成。委派 prompt 必须写明角色名（`sub-executor` / `eval-reviewer`）并明确要求其先完整读取对应的 `harness/roles/*.md` 与本次交接列出的文件；只委派这两个角色，不得生成其他 agent，子 agent 不得继续委派。
- LCA 知识与 openLCA 规则在 DSH 中均不全局加载；按 workflow 条件读取 `harness/rules/lca-knowledge/README.md` 与 `harness/rules/openlca-operation/README.md`。
- 无人值守：运行中不得征求用户建模决定、不得尝试扩大权限；运行启动即授权在当前预检范围完全一致时执行导入，预检通过后立即继续导入与报告，不得请求额外确认。
- 如果返回 `failed`，保留已记录状态并报告 `status_reason` 与确切问题。终止只有 `completed` 和 `failed`。
- 工作流产物只写 `workspace/memory/`、`workspace/outputs/inventory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/`；不要在别处写运行状态。
- DSH bash 单次调用有约 60 秒上限：预计耗时的命令（长脚本、批量处理）用 `run_in_background` 后台执行并轮询结果，不要阻塞等待超时。

## 禁止

- 不得在本 skill 中复制四阶段步骤、阶段 spec 路径列表或 schema 加载顺序（均由 workflow 定义）。
- 不得把 openLCA 清理或环境引导步骤写进本 skill（环境引导见 bootstrap-env 技能）。
