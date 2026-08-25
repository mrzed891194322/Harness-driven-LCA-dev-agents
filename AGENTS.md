# Whole-LCA 启动入口

业务运行的正式入口是各平台一行 CLI。不要把 IDE 对话当成 whole-lca / revise-lca 启动器；交互会话里的 `/whole-lca`、`$whole-lca` 与 CLI 调用同一套 command/skill。

环境引导例外：可以用命令行或对话执行 `src/scripts/proj_init/PROMPT.md`（`/bootstrap-env`、`$bootstrap-env`），不要加 `--agent major-orchestrator`。

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

编排步骤只在 `harness/workflows/LCA-main.md` 与 `harness/workflows/LCA-revise.md`。MCP 实现只在 `harness/tools/`（启动命令指向 `harness/tools/control_openlca/main.py`）。角色职责在 `harness/roles/`；各平台 adapter 只保留权限与启动指令。

## Claude Code

若 `claude --agent major-orchestrator -p "/whole-lca"` 不展开 slash command，改为：

```bash
claude --agent major-orchestrator -p "读取并执行 .claude/commands/whole-lca.md" --permission-mode dontAsk
```

revise-lca 同理，将 `whole-lca` 替换为 `revise-lca`。

## Codex

Codex 只作为 LCA 编排 agent，不要用它修改项目代码。只执行 `$bootstrap-env`、`$whole-lca`、`$revise-lca`；不要修改 harness、GUI、脚本或其他 tracked 源码。不要使用 `$improve-whole-lca-workflow`，也不要接受「先跑 LCA 再改 harness」的混合任务。

运行产物写在 `workspace/memory/`、`workspace/outputs/LCI/`、`workspace/outputs/reports/`；计划输入是 `workspace/inputs/plan.md`，修订意见是 `workspace/inputs/revise.md`。不要使用旧的 `workspace/plan/`、`workspace/LCI/`、`workspace/results/`。
