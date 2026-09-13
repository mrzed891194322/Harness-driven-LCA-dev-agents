---
id: 01-intake-gate
inputs:
  - workspace/inputs/plan.md
  - harness/knowledge/
outputs:
  - workspace/memory/reviews/01-intake-gate-1.md
---

# 01 初始化检查

工作流启动门禁，不是 ISO LCA 步骤。只派审查任务，不派执行任务，不跑校验脚本，不写 BOM、不查库、不导入。一次未通过即停止，不返工。

## 阶段目标

确认 `workspace/inputs/plan.md` 足以启动端到端 LCA，且 `harness/knowledge/` 中的资料能对上计划中点名的文件。

## 输入说明

- `workspace/inputs/plan.md`：研究对象与目的、功能单位（数值 + 描述 + 单位）、系统边界、截断或明确不截断、多产出/分配、预期应用或完成判断。缺一项、仍是模板占位或互相矛盾则未通过。
- `harness/knowledge/`：先读取 source_manifest 并按需列出不受 ignore 影响的目录，再下结论。计划里点名的资料必须对得上文件。目录空且计划声称有资料则未通过。不得编造「文件不存在」。

环境/CLI/openLCA 连通性由 GUI 或 CLI 在启动前探测。本阶段不调 `health_check`。不要因为计划缺少内部符号（如 `GAP-*`）而失败。

## 提交要求

审查任务提交 handoff（`passed` 或 `failed` + 非空 `status_reason`）。主编排把结论写入 `workspace/memory/reviews/01-intake-gate-1.md`。

## 验收标准

- 上述全部启动信息齐全且不互相矛盾。
- 知识目录已盘点；计划点名的资料有对应文件。
- 未通过则运行 `failed`，不进入 02。

## 前置及停止条件

无执行返工。一次审查失败即停止。

本阶段不要求逐行阅读全部资料；只读计划点名的必要段落以确认可启动，详细数据核查留给 02。
