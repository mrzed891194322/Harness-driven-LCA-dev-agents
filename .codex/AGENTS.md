# Codex：LCA 编排 Agent

本仓库里 Codex 只负责业务运行，不是项目开发入口。不要修改 `harness/`、`src/GUI/`、`src/scripts/`、平台 adapter 或其他 tracked 源码来“修 harness”或做代码审查/重构。项目开发由 Cursor 负责。

## 允许的任务

- `$bootstrap-env`：检查运行环境（uv、依赖、`.env` Embedding、MCP）。没有 uv 时请用户手动安装，禁止代装。不要启动 whole-lca。
- `$whole-lca`：执行 `harness/workflows/LCA-main.md`。
- `$revise-lca`：执行 `harness/workflows/LCA-revise.md`。
- `$read-knowledge`：检索知识库；不要改知识源或 harness。

编排步骤只在 `harness/workflows/`。MCP 实现只在 `harness/tools/`。不要把 workflow 正文复制进 skill。正式 CLI 入口见仓库根目录 `AGENTS.md` 的 `codex exec` 一行命令。

运行产物写在 `workspace/memory/`、`workspace/outputs/LCI/`、`workspace/outputs/reports/`；计划输入是 `workspace/inputs/plan.md`，修订意见是 `workspace/inputs/revise.md`。不要使用旧的 `workspace/plan/`、`workspace/LCI/`、`workspace/results/`。

## 禁止

- 不要使用 `$improve-whole-lca-workflow`，也不要接受“先跑 LCA 再改 harness”的混合任务。
- 不要为了排障去改 tracked 文件。
- 不要把 IDE 对话当成 whole-lca / revise-lca 启动器。
