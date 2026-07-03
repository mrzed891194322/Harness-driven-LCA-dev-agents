---
name: lca-specification
description: LCA（生命周期评估）项目执行计划与 LCI 数据构建的强工作流路由入口。制定计划、构建 LCI、生成映射、导入或自检时必须加载，并按本文件揭示的 harness/specs 路径读取规范。
---

# LCA 规范强路由 (lca-specification)

本技能负责把 LCA 工作流路由到 `harness/specs/` 中的最小必要规范，并明确每类工作必须读取哪些文件。

`harness/specs/` 是规范事实来源。不要一次性读取全部规范；按下方工作流卡片读取。

> [!IMPORTANT]
> **通用护栏**
> - 涉及 openLCA 背景数据、实体 UUID、模型图、导入或计算时，必须同时加载 `external-tools`，并使用正式工具查询。
> - 严禁凭空编造 UUID、Flow、Process、Provider 或 LCIA 方法。
> - 任何计划、LCI、映射报告必须保留数据来源、假设、不确定项和需要用户确认的事项。
> - 自检不通过时不得宣称完成；必须输出可执行的问题清单并回到相应 agent 修正。

---

## 工作流路由卡片

请根据当前任务类型读取对应的规范入口：

### A. 制定或修改 LCA 执行计划 / Todo
主要参考者：`plan-maker`

必读顺序：
1. `harness/specs/plan-guidelines/README.md`
2. `harness/specs/plan-guidelines/instructions/plan_guidance.md`
3. `harness/specs/plan-guidelines/template/execution_plan.md`
4. `harness/specs/plan-guidelines/template/todo_list.md`
5. `harness/specs/plan-guidelines/evaluation/self_check.md`

如计划需要确认 openLCA 当前状态，继续加载 `external-tools`，读取 `harness/tools/control_openlca/README.md`，再使用其揭示的正式工具。

### B. 构建 LCI JSON / 映射报告 / 导入 openLCA
主要参考者：`LCI-designer`

必读顺序：
1. `harness/specs/lci-construction/README.md`
2. `harness/specs/lci-construction/instructions/lci_construction.md`
3. `harness/specs/lci-construction/instructions/mapping_specification.md`
4. `harness/specs/lci-construction/instructions/import_specification.md`
5. `harness/specs/lci-construction/template/flow_example.json`
6. `harness/specs/lci-construction/template/process_example.json`
7. `harness/specs/lci-construction/template/product_system_example.json`
8. `harness/specs/lci-construction/template/human_readable_mapping.md`
9. `harness/specs/lci-construction/evaluation/self_check.md`

涉及背景数据库、UUID、模型图或导入时，继续加载 `external-tools`，读取 `harness/tools/control_openlca/README.md`。

### C. 无法判断
读取：`harness/specs/README.md`
