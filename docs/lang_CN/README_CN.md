# 中文文档

这里汇总 Harness-driven LCA Agents 的中文使用文档。首次使用建议按照“环境配置 →
项目准备 → GUI 或命令行运行”的顺序阅读。

## 首次使用

1. 满足 README 前置要求（uv、Codex / Claude Code / OpenCode 三者之一的 CLI，以及每次开工前打开 openLCA 并启用 IPC Server）。
2. 用命令行执行 `bootstrap-env`（或把 `src/scripts/setup_env/PROMPT.md` 发给 agent）。
3. 需要手动安装细节时看 [环境准备与配置](env_setup.md)。
4. [项目准备说明](project_prep.md)：准备计划、参考资料和 openLCA IPC Server。
5. 返回[项目 README](../../README.md) 运行 GUI 或 whole-lca。

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
