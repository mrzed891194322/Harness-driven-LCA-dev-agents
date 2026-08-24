# Claude Code

本仓库的 Whole-LCA 业务运行由 CLI 拉起，不要把 IDE 对话当成 whole-lca 启动器。

环境引导例外：可以执行 `/bootstrap-env`，或读取 `src/scripts/setup_env/PROMPT.md`。不要加 `--agent major-orchestrator`。

```bash
claude -p "/bootstrap-env"

claude --agent major-orchestrator -p "/whole-lca" --permission-mode dontAsk
claude --agent major-orchestrator -p "/revise-lca" --permission-mode dontAsk
```

若 `-p "/whole-lca"` 不展开 slash command，改为：

```bash
claude --agent major-orchestrator -p "读取并执行 .claude/commands/whole-lca.md" --permission-mode dontAsk
```

对应 OpenCode / Codex 一行命令见根目录 `AGENTS.md`。编排步骤只在 `harness/workflows/`；MCP 启动命令指向 `harness/tools/query_rag/main.py` 与 `harness/tools/control_openlca/main.py`。
