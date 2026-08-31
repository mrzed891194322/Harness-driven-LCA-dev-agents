# 01 初始化检查（eval-reviewer）

产物路径与一次未通过即停见 `harness/specs/01-intake-gate/`。本文件只写审查口径。

- 审 `workspace/inputs/plan.md` 能否启动端到端：研究对象与目的、功能单位的数值+描述+单位、系统边界、截断或明确不截断、多产出/分配、预期应用或完成判断。缺一项、仍是模板占位或互相矛盾则 `failed`。
- 审 `harness/knowledge/`：先列出目录再下结论。计划里点名的资料必须对得上文件。目录空且计划声称有资料则 `failed`。不得编造「文件不存在」。
- 不要因为计划缺少内部符号（如 `GAP-*`）而失败。
- 本阶段不调 `health_check`、不写 BOM、不查库、不导入。环境/CLI/openLCA 连通性由 GUI 或 CLI 在启动 agent 前探测。
