# LCA Agent 基准测试文档

本目录保存 Harness LCA Agent 的开发回归材料。它把固定案例、执行任务、运行证据和质量评价拆开，以便在 Agent、模型、提示词、知识库或 openLCA 环境变化后进行可复核的比较。

当前仅提供文档和模板，**尚未实现自动 benchmark runner**，也没有在本目录中保存可跨环境复用的 LCIA 数值金标。

## 文件导航

建议按以下顺序阅读：

1. [benchmark_plan.md](benchmark_plan.md)：基准的范围、固定输入、期望产物、评测维度和迭代方法。
2. [water_bottle_lca_plan.md](water_bottle_lca_plan.md)：可直接交给 Agent 执行的 PET 水瓶 Case 1/2/3 计划。
3. [agent_task_template.md](agent_task_template.md)：迁移到其他 LCA 案例时使用的通用任务模板。
4. [benchmark_run_record_template.md](benchmark_run_record_template.md)：记录一次可复现运行的环境、轨迹、差异和结论。
5. [lca_quality_evaluation.md](lca_quality_evaluation.md)：基于 ISO 14040/14044 的硬性门禁和项目自定义工程质量等级。

## 三类基准必须分开

| 类型 | 回答的问题 | 本目录中的示例 | 变更规则 |
| :--- | :--- | :--- | :--- |
| 案例事实金标 | Agent 是否保持了明确给定的功能单位、物料、运输量、边界和情景差异 | 1,000 个 1 L 瓶、PET 60 kg、Case 2 铁路 325 t·km | 只有案例定义被有意修订时才变更 |
| 特定 openLCA 环境数值基线 | 在锁定数据库、system model、Provider UUID、LCIA 方法和计算设置后，结果是否回归 | 某次运行记录中的各影响类别结果与贡献 | 环境或映射变化后必须重新评估，不得沿用旧结果 |
| 国际标准符合性评价 | 研究过程和报告是否覆盖适用的 ISO 14044 规范性要求 | 目标与范围、LCI、LCIA、解释、报告和关键审查门禁 | 随适用标准、修正案和研究用途复审 |

案例事实一致不代表 openLCA 结果一定相同；数值结果相近也不代表研究满足 ISO 要求。三者不得合并为一个模糊的“正确率”或总分。

## 使用边界

本目录的水瓶案例源于教学材料，目的是开发回归和工作流验证。它缺少工厂一手数据，并有明确的前景能耗、使用阶段和报废阶段缺口。因此：

- 不得把案例结果描述为某个实际产品的环境绩效；
- 不得据此作公开的产品优越性声明；
- 不得把自动评价、工程等级或一次成功计算称为 ISO 认证、合格证书或关键审查结论；
- 不得把教程使用的 ecoinvent 3.1 结果当作当前 ecoinvent 3.11 环境的严格数值金标。

每次运行应复制 [benchmark_run_record_template.md](benchmark_run_record_template.md)，锁定环境并保留原始证据，再根据 [lca_quality_evaluation.md](lca_quality_evaluation.md) 给出 `pass`、`conditional_pass`、`fail` 或 `needs_human_review`。
