# Whole-LCA 启动入口

业务运行的正式入口是各平台一行 CLI。不要把 IDE 对话当成 whole-lca / revise-lca 启动器；交互会话里的 `/whole-lca`、`$whole-lca` 与 CLI 调用同一套 command/skill。

环境引导例外：可以用命令行或对话执行 `src/scripts/setup_env/PROMPT.md`（`/bootstrap-env`、`$bootstrap-env`），不要加 `--agent major-orchestrator`。

在仓库根目录执行：

```bash
opencode run --command bootstrap-env
codex exec -s workspace-write '$bootstrap-env'
claude -p "/bootstrap-env"

opencode run --command whole-lca
opencode run --command revise-lca

codex exec -s workspace-write '$whole-lca'
codex exec -s workspace-write '$revise-lca'

claude --agent major-orchestrator -p "/whole-lca" --permission-mode dontAsk
claude --agent major-orchestrator -p "/revise-lca" --permission-mode dontAsk
```

编排步骤只在 `harness/workflows/LCA-main.md` 与 `harness/workflows/LCA-revise.md`。MCP 实现只在 `harness/tools/`。Codex 只作为 LCA 编排 agent，不要用它修改项目代码。
