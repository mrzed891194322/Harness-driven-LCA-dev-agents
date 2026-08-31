---
name: revise-lca
description: 从现有 LCA 最终报告、plan、LCI、运行 memory 和 workspace/inputs/revise.md 用户意见启动可追溯的完整修订，覆盖 plan 与最终报告并重新执行 openLCA/LCIA 门禁。适用于 revise-lca 或修改既有 LCA 结果。
whenToUse: 用户要求运行 revise-lca、按 workspace/inputs/revise.md 修订既有 LCA 结果并重算报告时。
---

# Revise-LCA 主工作流

将本技能作为 DSH 平台的 revise-lca 入口。修订专属契约位于
`harness/specs/08-lca-revise-workflow/`，01–04 编号包位于 `harness/specs/`；不要在 Agent 对话中重述或弱化。

## 启动

1. 当前 headless 会话即担任 `major-orchestrator`：先完整读取 `harness/roles/major-orchestrator.md` 的职责边界，再完整读取并执行 `harness/workflows/LCA-revise.md`。执行 workflow 中的 baseline 准备（`baseline.py snapshot --yes` 与 `activate --yes`）。GUI 或用户已前置 `clean_dir --preset revise-lca` 并完成文件就位；**不要**在 agent 内调用 `clean_dir` 或 MCP `cleanup_output`。固定意见输入为 `workspace/inputs/revise.md`；用户参考资料只从 `harness/knowledge/` 读取。不要再生成另一个 `major-orchestrator`。
2. 只生成 `sub-executor` 和 `eval-reviewer` 两个角色的子 agent。每次委派前后在用户可见输出中写明当前阶段、被委派角色、输入产物路径和等待原因；子 agent 返回后立即摘要结论与产物，不要用空的 Wait 心跳代替阶段进展。

## DSH 运行时补充

- workflow 文本中的 MCP 裸工具名在 DSH 中带前缀：`mcp__control_openlca__health_check` 等（`mcp__control_openlca__<原名>`）。若工具列表中不存在 `mcp__control_openlca__*` 工具，视为 openLCA 不可用：按 workflow 将运行置为 `failed` 并写非空 `status_reason`，不得绕过或重试。
- 子 agent 用 `subagent` 工具生成。委派 prompt 必须写明角色名（`sub-executor` / `eval-reviewer`）并明确要求其先完整读取对应的 `harness/roles/*.md` 与本次交接列出的文件；只委派这两个角色，不得生成其他 agent，子 agent 不得继续委派。
- LCA 知识与 openLCA 规则在 DSH 中均不全局加载；按 workflow 条件读取 `harness/rules/lca-knowledge/README.md` 与 `harness/rules/openlca-operation/README.md`。
- 无人值守：运行中不得征求用户建模决定、不得尝试扩大权限；预检成功后在同一 `import_scope` 下立即继续导入，不请求额外确认。
- 如果返回 `failed`，保留已记录状态并报告 `status_reason` 与确切问题。终止只有 `completed` 和 `failed`。
- 工作流产物只写 `workspace/memory/`、`workspace/outputs/inventory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/`；baseline 只读且不得覆盖。
- DSH bash 单次调用有约 60 秒上限：预计耗时的命令用 `run_in_background` 后台执行并轮询结果。

## 强制完成

- baseline 始终只读；候选计划通过审查后才覆盖 `workspace/inputs/plan.md`。
- 最多三次阶段审查返工；库名/分类/LCI 目录变化、部分导入、断链、空结果或资源未释放均停止。
- 最终报告覆盖 `workspace/outputs/reports/lca_report.md` 并包含修订摘要、用户意见落实矩阵和基线差异。

## 禁止

- 不得在本 skill 中复制阶段步骤、阶段 spec 路径列表或 schema 加载顺序（均由 workflow 定义）。
- 不得把 baseline 脚本的正文或 openLCA 清理步骤抄进本 skill（以 workflow 为准）。
