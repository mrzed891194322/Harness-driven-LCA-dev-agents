# 中文文档

这里汇总 Harness-driven LCA Agents 的中文使用文档。首次使用建议按照“环境配置 →
项目准备 → GUI 或命令行运行”的顺序阅读。

## 首次使用

1. [环境准备与配置](env_setup.md)：安装 uv、OpenCode，配置模型、Embedding 服务和
   Python 环境。
2. [项目准备说明](project_prep.md)：准备计划、参考资料和 openLCA IPC Server。
3. 返回[项目 README](../../README.md)，按照“快速开始”和“使用 GUI 完成一次 LCA”
   运行工作流。

## 专题指南

| 文档 | 适用场景 |
| --- | --- |
| [RAG 构建与查询](rag_guide.md) | 了解知识库类型、重建方式、查询参数和测试 |
| [手动调试与文件同步](manual_debug.md) | 不使用 GUI、检查固定路径或手动执行 whole-lca / revise-lca |
| [GUI 模块说明](../../src/GUI/README.md) | 了解当前界面功能、状态门禁和 GUI 开发约定 |

## 运行前须知

> [!WARNING]
> `whole-lca` 会清理活动数据库中当前项目分类下已有的前景实体，并清理
> `workspace` 中除输入外的旧生成物。默认手动初始化也会执行清理。运行前请确认活动
> 数据库、项目分类和输入资料无误。

运行状态以 `workspace/memory/manifest.json` 为准。只有状态为 `completed` 且报告、
模型图和计算结果齐备时，才能认为流程完整结束；`needs_input`、`needs_review` 和
`failed` 都需要根据保存的阶段证据继续处理。
