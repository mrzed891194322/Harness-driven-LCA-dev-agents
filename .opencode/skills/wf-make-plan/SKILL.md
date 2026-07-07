---
name: wf-make-plan
description: LCA 执行计划与 Todo 制定/修改工作流。制定、修订或自检计划时必须加载。
---

# LCA 项目计划制定工作流

本技能为负责 LCA 执行计划与 Todo List 制定的 Agent 提供执行逻辑与步骤参考。

在分析、制定或修订方案时，必须遵循以下执行逻辑。

## 1. 计划制定核心工作流

### 第一步：读取输入与界定任务场景

- 读取用户需求、用户提供的参考资料、已有计划文档和已有 Todo 文档。
- 判断当前任务属于新计划制定还是老计划修改。
- 若任务范围不清，先读取 `harness/specs/README.md` 作为路由索引，再进入最小相关规范。

### 第二步：新计划制定

适用条件：`workspace/plan/execution_plan.md` 和 `workspace/plan/todo_list.md` 尚不存在，或用户发起全新的项目计划制定。

- 完整读取命令中指定的初始化需求文档及相关参考背景文档。
- 建立计划内容与字段结构时，必须显式读取并遵守：
  - `harness/specs/plan-guidelines/references/plan_spec.md`
- 围绕研究对象、目的、功能单位、系统边界、截断规则、分配原则、LCIA 方法、数据基础、openLCA 环境、模型架构和验证解释方案建立计划框架。
- 使用 `harness/specs/plan-guidelines/references/template/execution_plan.md` 形成 `workspace/plan/execution_plan.md`。
- 将所有无法确定的信息、缺口数据和决策项汇总到 `workspace/plan/todo_list.md`。
- `todo_list.md` 必须使用 `harness/specs/plan-guidelines/references/template/todo_list.md`。

### 第三步：老计划修改

适用条件：已有 `workspace/plan/execution_plan.md` 和 `workspace/plan/todo_list.md`，且用户通过交互界面或修改文件提供了具体反馈。

- 首先完整读取现有 `workspace/plan/execution_plan.md` 和 `workspace/plan/todo_list.md`。
- 修订计划内容与 Todo 结构时，必须显式读取并遵守：
  - `harness/specs/plan-guidelines/references/plan_spec.md`
- 提取用户在各个 `***✍️ 用户填写内容区***` 内填写的最新反馈、答复内容和额外修改需求。
- 严禁随意推翻或重新生成与用户反馈无关的已有设计。
- 基于用户反馈对 `execution_plan.md` 的对应模块进行局部精准修正与细节丰富。
- 一旦用户对某个待完善清单条目做出明确答复，必须同步更新或标记 `todo_list.md` 中对应条目，并把已解决内容固化进执行计划。

### 第四步：openLCA 与外部数据确认

- 如计划依赖 openLCA 当前状态、背景数据库、LCIA 方法、实体 UUID、模型图、导入或计算结果，必须加载 `tu-control-openlca` 并使用正式工具查询。
- 严禁凭空编造 UUID、Flow、Process、Provider、LCIA 方法、数据库状态或 openLCA 连接状态。
- 对仍无法确认的数据、假设和决策，必须记录到 Todo，而不是写成确定事实。

### 第五步：计划自检与 Agent 循环

- 生成或修订计划文件后，必须调用评估环节进行质量与规范性检查。
- 要求 `eval-executor` 显式读取并对照此验收与自检规范执行验证：
  - `harness/specs/plan-guidelines/references/eval_spec.md`
- 如果评估结论为“需要改进”，必须根据反馈重新调度文档修改，随后再次提交评估。
- 循环迭代直到评估结论为达标或可交付。

## 2. 规范化输出目录要求

所有计划阶段产物必须集中放置于 `workspace/plan/`。

- 执行计划：`workspace/plan/execution_plan.md`
- 待完善清单：`workspace/plan/todo_list.md`

## 3. 完成交付条件

- `execution_plan.md` 满足 `harness/specs/plan-guidelines/references/plan_spec.md` 和执行计划模板要求。
- `todo_list.md` 满足 `harness/specs/plan-guidelines/references/plan_spec.md` 和 Todo 模板要求。
- 所有数据来源、假设、不确定项和需要用户确认的事项均已明确记录。
- 自检通过；如未通过，不得宣称完成，必须输出可执行的问题清单并返回修正。
