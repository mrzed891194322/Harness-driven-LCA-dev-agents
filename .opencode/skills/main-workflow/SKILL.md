---
name: main-workflow
description: "兼容性的 harness LCA 工作流路由入口。保留给现有 major-orchestrator 使用；具体任务规范仍以 harness/specs 与 harness/rules 为事实来源。"
---

# harness LCA 工作流路由 (main-workflow)

本技能暂时作为 `major-orchestrator` 的兼容入口保留。它只说明工作流阶段与子 Agent 路由，不维护 LCA 业务规范、文件模板或工具命令。

事实来源：

- LCA 计划与 LCI 构建规范：`harness/specs/`
- 项目规则、目录与调用边界：`harness/rules/`
- openLCA/RAG 工具说明与脚本：`harness/tools/`

## 标准阶段

完整 LCA 任务按以下阶段路由：

### 1. 计划与方案制定
- **Agent**：`plan-maker`
- **调用路径**：`subagents/workflow/plan-maker`
- **规范入口**：通过 `lca-specification` 读取 `harness/specs/plan-guidelines/README.md`

### 2. LCI 结构化构建与导入
- **Agent**：`LCI-designer`
- **调用路径**：`subagents/workflow/LCI-designer`
- **规范入口**：通过 `lca-specification` 读取 `harness/specs/lci-construction/README.md`

### 3. 评估、归档与交付
- **Agent**：`eval-executor`、`doc-handler`
- **评估调用路径**：`subagents/workflow/eval-executor`
- **文档/归档调用路径**：`subagents/tools/doc-handler`
- **规则入口**：通过 `project-regulation` 读取 `harness/rules/` 中的最小必要规则

---

## 选择性执行原则

对于追加修改任务，定位受影响的最小阶段并按需执行：

- 计划、需求或待完善事项变化：调用 `plan-maker`。
- LCI 映射、JSON 结构或导入逻辑变化：调用 `LCI-designer`，必要时再调用 `eval-executor`。
- 文件写入、归档、模板化文档更新：调用 `doc-handler`。
- 代码或脚本修改：调用 `code-builder`，并按 `project-regulation` 读取编码规范。

`data-processor` 仅作为可选的非主线数据预处理 Agent 使用；除非任务明确涉及独立数据清洗、划分或特征工程，否则不要把它纳入标准 LCA 工作流。
