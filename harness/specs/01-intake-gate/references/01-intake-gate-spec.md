# 01 初始化检查

## 谁做

主编排只委派 `eval-reviewer`。不委派 `sub-executor`，不跑校验脚本，不写 BOM、不查库、不导入。

## 看什么

- `workspace/inputs/plan.md`：能否启动端到端（研究对象与目的、功能单位的数值+描述+单位、系统边界、截断或明确不截断、多产出/分配、预期应用或完成判断）。缺一项、仍是模板占位或互相矛盾则 `failed`。
- `harness/knowledge/`：目录能否盘点；计划里点名的资料对得上文件。目录空且计划声称有资料则 `failed`。不要编造「文件不存在」——先列出目录再下结论。

环境/CLI/openLCA 连通性由 GUI 或 CLI 在启动 agent 前探测。本阶段不调 `health_check`。

## 输出

审查笔记：`workspace/memory/reviews/01-intake-gate-1.md`（`passed` 或 `failed` + 摘要）。一次未通过即停，不返工。
