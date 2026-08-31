# 仓库环境引导

你是当前会话的根 agent。只执行本文件。不要委派 `major-orchestrator` / `sub-executor`，不要启动 whole-lca / revise-lca。

## 禁止

- 不得安装 uv（不得执行官方安装脚本、`pip install uv`、包管理器安装或其它代装动作）。
- 不得把 uv 安装命令写进你自己要跑的步骤里。安装说明只存在于 `docs/lang_CN/env_setup.md`，留给用户。
- 不得清理 workspace，不得启动 whole-lca / revise-lca。
- 不要把 `.env` 全文贴进对话。
- 不得改写用户全局配置（例如 `~/.dsh/`、各 CLI 的用户级审批设置）。只建议，不代改。

## Phase 0：检查 uv

在仓库根目录执行：

```bash
command -v uv || where uv
uv --version
```

若命令不存在或 `uv --version` 失败：整次引导 **不通过**。原样输出下面这一句，然后停止，不要继续 `uv sync`：

`环境检测不通过：未找到 uv。请按 docs/lang_CN/env_setup.md 手动安装 uv 后重试。`

## Phase 1：同步并检查项目环境

uv 可用之后，在仓库根目录执行：

```bash
uv sync
uv run python src/scripts/proj_init/main.py
```

以脚本退出码和结尾 `--- json ---` 之后的 JSON 为准。

- 退出码 `1`：必要项失败（无 uv、sync 失败、Python 版本不对、`control_openlca` MCP import 失败）。按脚本输出汇报，不要自行安装软件。
- 退出码 `0`：必要项通过。脚本若因缺少 `.env` 而从 `.env.example` 复制，只报告「已从模板创建」，不要打开 `.env` 把内容贴进对话。
- JSON 中的 `harness_clis` 列出 `opencode` / `claude` / `codex` / `dsh` 各自是否在 PATH。缺某一个不失败；四个都没有也不把本次引导打成退出码 1。

## Phase 2：Agent CLI 与 auto-review

根据 Phase 1 JSON 的 `harness_clis.clis`，逐项汇报每个 CLI「可用」或「未安装」。

- 四个都没有：标明 **GUI 路径不可用**（GUI 必须在 PATH 上有所选 CLI）。当前会话仍可完成引导。
- 对每个 **可用** 的 CLI，建议用户将其调整为 auto-review / 自动批准（只建议，不要改用户全局配置）：
  - **OpenCode**：在 OpenCode（TUI / Desktop / 插件）中开启自动批准或 skip permissions。GUI 启动已带 `--dangerously-skip-permissions`。
  - **Claude Code**：本仓库 `.claude/settings.json` 已是 `bypassPermissions`。插件 / Desktop 请确认跳过权限与 Auto-accept；CLI 可用 `--permission-mode dontAsk`。
  - **Codex**：将审批设为 Auto，不要逐条 Ask。CLI 使用 `workspace-write`。不要擅自改仓库里 MCP 的 `default_tools_approval_mode`。
  - **DSH**：会话或环境使用 `DSH_PERMISSION_MODE=danger-full-access`。不要写 `~/.dsh/` 仓库配置。

当前正在使用的 AI 工具（CLI / 插件 / Desktop）若也要无人值守跑 LCA，同样请打开该工具的自动批准。

## Phase 3：openLCA IPC

在仓库根目录执行：

```bash
uv run python src/scripts/check_status/main.py --only openlca
```

- 成功：openLCA 记为通过。
- 失败：记为「需你动手」——打开 openLCA 桌面客户端、打开目标数据库、启用 IPC Server（默认 `127.0.0.1:8080`），说明见 `docs/lang_CN/env_setup.md`。**不要**因此把 Phase 1 的退出码改写成失败；IPC 失败不是 uv / 依赖 / MCP import 失败。
- 不要对 openLCA 做写入、清理或导入。

## 汇报（中文）

逐项给出 `通过 / 已修复 / 需你动手`：

1. uv
2. 项目依赖（`uv sync` / Python）
3. `.env`（已存在，或已从模板创建）
4. MCP 接线（`control_openlca`）
5. Agent CLI：分别列出 opencode / claude / codex / dsh，并对每个可用项附上 auto-review 建议
6. openLCA IPC

最后一句：下一步可启动 GUI（见 `README.md`），或在所用的 Codex / Claude Code / OpenCode / DSH（CLI、IDE 插件或 Desktop）中，于完成 `clean_dir` 并放入资料后输入 whole-lca / revise-lca 指令。不要在本次引导里启动 whole-lca。
