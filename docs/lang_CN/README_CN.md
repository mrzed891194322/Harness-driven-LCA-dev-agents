# 中文文档

这里汇总 Harness-driven LCA Agents 的中文使用文档。首次使用建议：配环境 → 开 GUI 做初始化检查并跑计划。

## 首次使用

1. 满足 README 前置要求（uv、Codex / Claude Code / OpenCode 三者之一的 CLI，以及每次开工前打开 openLCA 并启用 IPC Server）。
2. 用命令行执行 `bootstrap-env`（或把 `src/scripts/proj_init/PROMPT.md` 发给 agent）。
3. 按[项目 README](../../README.md) 启动 GUI：设置&初始化 → 开始初始化检查 → 开始LCA工作 → 执行LCA计划。
4. 检查未通过时：uv 细节见 [环境准备与配置](env_setup.md)，openLCA IPC 见 [项目准备说明](project_prep.md)。

## 专题指南

| 文档 | 适用场景 |
| --- | --- |
| [项目 README](../../README.md) | GUI 使用：初始化检查、填写或上传计划、执行 LCA |
| [环境准备与配置](env_setup.md) | 手动安装 uv、`uv sync`、命令行检查 openLCA |
| [项目准备说明](project_prep.md) | openLCA IPC 截图；不用 GUI 时的输入路径 |
| [手动调试](manual_debug.md) | 不使用 GUI、检查固定路径或手动执行 whole-lca / revise-lca |
| [GUI 模块说明](../../src/GUI/README.md) | 界面功能、状态门禁和 GUI 开发约定 |

## 运行前须知

> [!WARNING]
> `whole-lca` 会清理活动数据库中当前项目分类下已有的前景实体，并清理
> `workspace` 中除输入外的旧生成物。默认手动初始化也会执行清理。运行前请确认活动
> 数据库、项目分类和输入资料无误。

运行状态以 `workspace/memory/manifest.json` 为准。只有状态为 `completed` 且报告、
模型图和计算结果齐备时，才能认为流程完整结束；`failed` 需要根据
`status_reason` 和保存的阶段证据继续处理。
