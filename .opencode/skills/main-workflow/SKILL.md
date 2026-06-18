---
name: main-workflow
description: "定义了 harness LCA 输出任务的标准工作流及各个步骤的执行规范。供 major-executor 等 agent 参考，以按需或完整调用相应的子 agent 执行任务。"
---

# harness LCA 任务工作流 (workflow)

本技能定义了 harness LCA 输出任务的标准工作流。主要用于指导 `major-executor` 等核心编排 Agent，根据任务类型（从头开始或追加修改）决定是完整执行整个流程，还是选择性按需执行特定步骤。

## 工作流抽象说明

在 harness LCA 任务中，标准的工作流程被拆分为多个解耦的步骤。每一个步骤均对应一个具备专门能力的子 Agent。当需要执行某一环节时，主 Agent 应调用对应的子 Agent（或技能）来完成，而非亲自执行。

## 标准工作流步骤及对应子 Agent

按照执行的先后顺序，完整的工作流包含以下环节：

### 1. 计划与方案制定 (plan-maker / pipeline-designer)
- **职责**：读取原始任务要求、数据说明，制定包含数据处理、LCA 计算细节以及最终交付标准的详细实施方案。
- **触发时机**：从头开始新任务，或用户大幅度改变任务目标、优化路线时。
- **调用路径**：`subagents/workflow/plan-maker` 或 `subagents/workflow/pipeline-designer`

### 2. 数据处理与清洗 (data-processor)
- **职责**：执行数据的读取、清洗、特征提取或格式转换。设计并产生预处理产物，供下游环节使用。
- **触发时机**：完整流程中必须执行；或用户追加要求补充新特征、修改数据处理逻辑时。
- **调用路径**：`subagents/workflow/data-processor`

### 3. 模型搭建与计算 (model-trainer)
- **职责**：负责 LCA 相关的脚本编写、配置运行以及计算逻辑的实现，并得出初步验证结果或预测值。
- **触发时机**：完整流程中必须执行；或涉及计算逻辑、代码实现、配置文件修改时。
- **调用路径**：`subagents/workflow/model-trainer`

### 4. 评估与验证 (eval-reviewer)
- **职责**：分析计算出来的指标、误差、数据复现性，并比对交付标准。明确输出结论：是否达标，是否需要下一轮优化。
- **触发时机**：任何涉及到模型、数据、验证脚本的改动产生新结果后，都必须强制调用进行评估。
- **调用路径**：`subagents/workflow/eval-reviewer`

### 5. 归档与交付输出 (output-checker)
- **职责**：接收 `eval-reviewer` 的评估结论。根据交付标准强制执行工作流分支决断。如果决定停止并交付，必须首先将结果归档至 `history/runN/`，然后再整理至最终的交付物目录 `output/`。
- **触发时机**：每次有评估结论产生后，必须强制由该步骤收尾决断和存档输出。
- **调用路径**：`subagents/workflow/output-checker`

---

## 灵活调用原则（选择性执行）

**对于用户后续的追加修改任务，应当避免机械地重复整个工作流**。请根据实际需求定位受影响的最小环节并按需执行：

- **若是纯文档/要求补充**：直接调用 `plan-maker` 或相应的辅助工具。
- **若是修正某个数据处理逻辑**：调用 `data-processor` 重新处理，再传给 `model-trainer` 验证，最后 `eval-reviewer` 评估，由 `output-checker` 存档。
- **若是仅需修改计算逻辑（无数据变更）**：跳过数据处理，直接调用 `model-trainer`。

**要求**：所有相关 Agent 必须牢记自己在工作流中的分工定位，遵守**最小化按需执行**的原则。
