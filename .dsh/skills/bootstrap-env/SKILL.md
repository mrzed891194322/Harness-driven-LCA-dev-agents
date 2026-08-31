---
name: bootstrap-env
description: 检查并配置本仓库运行环境：uv、openLCA、可用 Agent CLI 与 auto-review 建议。适用于初始化、bootstrap-env 或首次配环境。没有 uv 时判定不通过并请用户手动安装，禁止代装。不要启动 whole-lca。
whenToUse: 用户要求 bootstrap-env、初始化或首次配置本仓库运行环境时。
---

读取并执行 `src/scripts/proj_init/PROMPT.md`。不要改写其中的步骤。不要启动 whole-lca。

DSH 注记：按 PROMPT.md 逐项汇报。无人值守请使用 `DSH_PERMISSION_MODE=danger-full-access`。不要代装 uv，不要把 `.env` 全文贴进对话，不要写 `~/.dsh/`。
