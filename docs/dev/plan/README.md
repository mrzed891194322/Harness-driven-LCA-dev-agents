---
plan_kind: harness_lca_evergreen_plan
plan_version: "1.0"
status: active
current_maturity: M0
last_reviewed: 2026-07-19
---

# Harness LCA Agent 常青计划

## 1. 目的

本目录是 Harness LCA Agent 的长期规划源，用于持续提高 agent 工作流的标准符合性、准确性、可追溯性和可复现性。规划重点是 `agent`、`skill`、`spec`、`rule`、`tool`，并覆盖支撑它们的知识、状态、评测和可观测性。

本计划不以增加提示词或 agent 数量作为进展；只有形成了明确契约、可执行验证和可复核证据，能力才算完成。

> 当前采用仓库约定要求未来 agent 阅读本目录，尚未通过根级 `AGENTS.md` 或自动检查强制执行。未读风险由开发流程承担。

## 2. 开发前必读协议

未来 agent 在修改 Harness 前，按以下顺序读取最小必要内容：

1. 阅读本文件，确认范围、职责边界、权威来源和当前成熟度。
2. 阅读 [roadmap.md](roadmap.md) 的当前成熟度阶段、相关工作流和退出条件。
3. 阅读 [quality-gates.md](quality-gates.md)，确定本次变更的风险级别、必跑验证和人工审核要求。
4. 阅读 [decisions.md](decisions.md) 中仍有效的决定；若实现与既有决定冲突，先新增或替代决定，不得静默偏离。
5. 再按 `harness/specs/README.md`、相关 skill 的渐进披露路径读取任务级材料。

开发完成后：

- 在路线图对应交付物下附上测试、运行记录、评估报告或审核结论等证据。
- 只有满足全部退出条件，才可更新成熟度或标记阶段完成。
- 新增跨任务约束、接口或重大取舍时，同步更新本目录；纯任务进度不要写入决策记录。
- 若发现计划与代码不一致，先把差异记录为缺口，不能仅修改文档来掩盖实现问题。

## 3. 规划边界

### 3.1 范围内

- agent 角色、权限、委派关系和失败升级。
- skill 工作流、前置条件、后置条件和恢复路径。
- spec 输出契约、schema、模板和验收定义。
- rule 跨任务不变量、安全约束和禁止行为。
- tool 的类型化接口、确定性校验、只读/写入边界、幂等性和审计。
- RAG 知识、来源追溯、运行状态、日志、评测基准与专家审核。
- 实现端到端 LCA 所必需的 openLCA 接口契约。

### 3.2 范围外

- GUI 视觉、一般产品体验、用户与权限管理、云部署和商业化路线。
- 对未纳入本地知识库的行业 PCR、EPD 或产品碳足迹规则作合规承诺。
- 宣称本系统或其输出已获认证。ISO 14040/14044 是方法基线，不等同于认证结论。

## 4. 当前基线

| 能力 | 当前状态 | 主要证据 | 核心缺口 |
| :--- | :--- | :--- | :--- |
| LCA 计划制定 | 已有 agent、skill、spec、模板和自检 | `.opencode/agents/plan-maker.md`、`harness/specs/plan-guidelines/` | 评测以结构检查为主，缺少事实正确性基准 |
| LCI 构建与导入 | 已有 LCI 工作流、JSON 示例、映射及导入工具 | `.opencode/skills/wf-lci-construction/`、`harness/specs/lci-construction/` | 缺少统一机器 schema、数值语义验证和系统化回归集 |
| 知识检索 | 已有标准、openLCA、用户资料分库 RAG 和可追溯片段 | `harness/tools/query_rag/`、`harness/knowledge/` | 缺少证据覆盖率门禁、版本影响分析和冲突治理 |
| openLCA 控制 | 已有查询、导入、模型图与计算等工具基础 | `harness/tools/control_openlca/` | 接口和副作用边界仍需统一，集成测试覆盖有限 |
| LCIA、解释与报告 | 存在部分计算工具，尚未形成完整 agent 工作流 | `harness/tools/control_openlca/calculate_product_system/` | 缺少解释、完整性/一致性/敏感性检查、报告与审查闭环 |
| 评测与状态 | 已有任务内自检 agent | `.opencode/agents/subagents/workflow/eval-executor.md` | 缺少固定基准、跨版本指标、运行轨迹、断点恢复和发布门禁 |

因此当前成熟度为 **M0：治理基线**。现有功能可继续使用，但不能据此宣称已经实现完整、高准确或可独立审查的 LCA。

## 5. Harness 构件职责

| 构件 | 唯一主要职责 | 应包含 | 不应包含 |
| :--- | :--- | :--- | :--- |
| `agent` | 角色判断与任务编排 | 目标、权限、可调用角色、升级边界 | 复制完整业务规范或工具实现 |
| `skill` | 可复用工作流 | 触发条件、步骤、分支、前后置条件、恢复策略 | 重复 schema 字段或隐藏确定性计算 |
| `spec` | 产物与接口契约 | 结构、语义、模板、验收、兼容规则 | agent 调度细节 |
| `rule` | 跨任务不变量 | 安全约束、禁止行为、目录和编码约定 | 单个业务流程的完整步骤 |
| `tool` | 确定性能力与受控副作用 | 类型化输入输出、校验、错误码、审计、幂等策略 | 依赖自然语言判断来完成可编程校验 |

新增内容应先归入唯一主构件；确需跨层引用时，以链接指向单一事实源，避免复制。

## 6. 事实与规范优先级

发生冲突时，按以下顺序处理，并保留冲突记录：

1. 适用于研究目标的标准原文和经确认的外部规则。
2. 用户明确提供且适用于当前研究的事实、数据和决策。
3. openLCA 当前数据库、LCIA 方法和实体的工具查询结果。
4. `harness/specs/` 中的项目契约。
5. `harness/rules/` 和已加载 skill 的工作流约束。
6. agent 推断；推断必须标记，不能覆盖更高优先级证据。

第一阶段标准基线：

- [ISO 14040:2006 本地原文](<../../harness/knowledge/inputs/static_ref/standards/ISO14040-2006/ISO 14040-2006_.md>)：原则、框架、四阶段及迭代性。
- [ISO 14044:2006 本地原文](<../../harness/knowledge/inputs/static_ref/standards/ISO14044-2006/ISO 14044-2006_.md>)：要求与指南，包括解释、报告和关键审查。
- 本地已有修正案纳入知识库，但每次引用时仍需确认适用版本和具体条款。

## 7. 文档导航与维护

- [roadmap.md](roadmap.md)：成熟度阶段、持续工作流、交付物和退出条件。
- [quality-gates.md](quality-gates.md)：风险分级、零容忍项、评测指标和发布判定。
- [decisions.md](decisions.md)：长期有效的架构与治理决定。
- `docs/TODO.md`：历史和短期待办参考，不作为长期成熟度的完成证据；M0 阶段需逐项归并或关闭其中仍有效的内容。

至少在以下事件发生时复审本计划：标准或 openLCA 接口版本变化；新增 LCA 阶段；基准集发现关键错误；构件职责调整；准备对外发布比较性结论。

