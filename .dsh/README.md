# 项目级 DSH 配置

本目录存放本项目在 DeepSeek Harness（DSH，CLI：`dsh`）中的项目级配置：MCP 接线与可选 preset。whole-lca / revise-lca 由 Python 主编排驱动，DSH 只作为 worker。

| 其他平台 | DSH |
|---|---|
| `.codex/config.toml`（`[mcp_servers.control_openlca]`） | `.dsh/cordis.patch.yml`（`mcp-control_openlca` 行） |
| 无 named agent | `.dsh/agent-presets/lca/`（顶层会话 persona，不是主编排） |

## 目录结构

```
.dsh/
├── cordis.patch.yml
└── agent-presets/
    └── lca/
```

## GUI / 主编排

GUI 与无 GUI 用户都跑：

```bash
DSH_PERMISSION_MODE=danger-full-access uv run python src/scripts/lca_orchestrator/main.py --task whole-lca --worker dsh
DSH_PERMISSION_MODE=danger-full-access uv run python src/scripts/lca_orchestrator/main.py --task revise-lca --worker dsh
```

`DSH_PERMISSION_MODE=danger-full-access` 是无人值守必需：默认 `workspace-write` 沙箱会把缓存目录只读挂载，`uv run` 可能失败。

## 生效方式

- **SDK / 主编排 worker**：`deepseek-harness-sdk` 使用 `profile=sdk` 与 `--patch` 等价的 `patches=('.dsh/cordis.patch.yml',)`，并显式 `dsh_home`，不读 `~/.dsh` 当项目配置。
- **交互会话**：启动时传入 `--patch .dsh/cordis.patch.yml`，不写任何 `~/.dsh` 仓库配置。

## 已配置内容

### control_openlca MCP

见 `.dsh/cordis.patch.yml`。模型侧工具名可能为 `mcp__control_openlca__<rawName>`。不要设 `failOnStartupError: true`。

### Agent preset

`agent-presets` 行的 `roots` 追加 `.dsh/agent-presets`。persona 只说明本仓库由 Python 主编排驱动，不要把当前会话当成主编排。

## 前置条件

- PATH 上有 `dsh`，或由 SDK 绑定的 runtime；凭证由 DSH 自身管理，不写进仓库。
- whole-lca / revise-lca 还需 openLCA 桌面端 + IPC Server（见 `README.md`）。
